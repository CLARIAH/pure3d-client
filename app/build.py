import sys
import re

from pybars import Compiler
from markdown import markdown

from files import (
    dirContents,
    dirUpdate,
    dirNm,
    baseNm,
    stripExt,
    abspath,
    readYaml,
    readJson,
    writeJson,
    initTree,
    dirAllFiles,
    expanduser as ex,
)
from generic import AttrDict
from helpers import console
from tailwind import Tailwind


COMMENT_RE = re.compile(r"""\{\{!--.*?--}}""", re.S)

CONFIG_FILE = "config.yaml"
TAILWIND_CFG = "tailwind.config.js"


class Build:
    def __init__(self):
        baseDir = dirNm(dirNm(abspath(__file__)))
        localDir = f"{baseDir}/_local"

        cfgFile = f"{baseDir}/{CONFIG_FILE}"
        cfg = readYaml(asFile=cfgFile)
        self.cfg = cfg

        locations = cfg.locations
        self.locations = locations

        self.markdownKeys = set(cfg.markdown.keys)

        for k, v in locations.items():
            v = v.replace("«base»", baseDir)
            locations[k] = ex(v)

        locations.baseDir = baseDir
        locations.localDir = localDir

        self.Handlebars = Compiler()

        initTree(locations.dataIn, fresh=False)

        T = Tailwind(locations, TAILWIND_CFG)
        T.install()
        self.T = T

        self.rawData = AttrDict()
        self.data = AttrDict()

    def getRawData(self):
        rawData = self.rawData

        locations = self.locations
        dataInDir = locations.dataIn
        dbDir = f"{dataInDir}/db/json"

        for kind in ("site", "project", "edition"):
            rawData[kind] = readJson(asFile=f"{dbDir}/{kind}.json")

    def htmlify(self, info):
        markdownKeys = self.markdownKeys

        r = AttrDict()

        for (k, v) in info.items():
            r[k] = markdown(v) if k in markdownKeys else v

        return r

    def getData(self, target):
        rawData = self.rawData
        data = self.data
        pMap = self.pMap
        eMap = self.eMap

        if target in data:
            return data[target]

        info = rawData[target]

        # print(f"{target=}\n\n")
        # print(f"{info=}\n\n\n\n\n")

        if target == "site":
            item = info[0]
            dc = self.htmlify(item.dc)

            r = AttrDict()
            r.template = "p3d-home.html"
            r.file_name = "index.html"
            r.title = dc.title
            r.contentdata = dc
            r.projects = self.getData("project")
            r.editions = self.getData("edition")

            result = r

        elif target == "project":
            result = []

            for item in info:
                itemId = item._id["$oid"]
                itemNo = pMap.get(itemId, itemId)
                r = AttrDict()
                r.peName = item.title
                r.prId = itemNo
                r.peLink = f"project/{itemNo}.html"
                r.peDescription = item.dc.description
                r.peAbstract = item.dc.abstract
                r.peVisible = item.isVisible
                r.peSubjects = item.dc.subject
                r.isTypeProject = True
                result.append(r)

        elif target == "edition":
            result = []

            for item in info:
                itemId = item._id["$oid"]
                itemProjectId = item.projectId["$oid"]
                itemProjectNo = pMap.get(itemProjectId, itemProjectId)
                itemNo = eMap.get(itemProjectId, {}).get(itemId, itemId)
                r = AttrDict()
                r.peName = item.title
                r.prId = itemProjectId
                r.edId = itemNo
                r.peLink = f"project/{itemProjectNo}/edition/{itemNo}.html"
                r.peDescription = item.dc.description
                r.peAbstract = item.dc.abstract
                r.pePublished = item.isPublished
                r.peSubjects = item.dc.subject
                r.isTypeEdition = True
                result.append(r)

        else:
            result = None

        data[target] = result
        return result

    def generate(self):
        locations = self.locations
        dataInDir = locations.dataIn
        dataOutDir = locations.dataOut
        filesInDir = f"{dataInDir}/files"
        projectInDir = f"{filesInDir}/project"
        templateDir = locations.templates
        filesOutDir = f"{dataOutDir}/files"
        projectOutDir = f"{filesOutDir}/project"
        Handlebars = self.Handlebars
        partialsIn = locations.partialsIn
        T = self.T

        partials = {}
        self.partials = partials

        def copyFromExport():
            """Copies the export data files to the static file area.

            The copy is incremental at the levels of projects and editions.

            That means: projects and editions will not be removed from the static file
            area.

            So if your export contains a single or a few projects and editions,
            they will be used to update the static file area without affecting material
            of the static file area that is outside these projects and editions.
            """

            goodOuter, cOuter, dOuter = dirUpdate(filesInDir, filesOutDir, recursive=False)
            c = cOuter
            d = dOuter

            pMap = {}
            eMap = {}
            self.pMap = pMap
            self.eMap = eMap

            pCount = 0

            for pNum in dirContents(projectOutDir)[1]:
                pId = readJson(asFile=f"{projectOutDir}/{pNum}/id.json").id
                pMap[pId] = pNum

            for pId in dirContents(projectInDir)[1]:
                if pId in pMap:
                    pNum = pMap[pId]
                else:
                    pCount += 1
                    pNum = pCount
                    pMap[pId] = pNum

                pInDir = f"{projectInDir}/{pId}"
                pOutDir = f"{projectOutDir}/{pNum}"
                goodProject, cProject, dProject = dirUpdate(
                    pInDir, pOutDir, recursive=False
                )
                c += cProject
                d += dProject
                writeJson(dict(id=pId), asFile=f"{projectOutDir}/{pNum}/id.json")

                editionInDir = f"{pInDir}/edition"
                editionOutDir = f"{pOutDir}/edition"

                eCount = 0

                thisEMap = {}

                for eNum in dirContents(editionOutDir)[1]:
                    eId = readJson(asFile=f"{editionOutDir}/{eNum}/id.json").id
                    thisEMap[eId] = eNum

                for eId in dirContents(editionInDir)[1]:
                    if eId in thisEMap:
                        eNum = thisEMap[eId]
                    else:
                        eCount += 1
                        eNum = eCount
                        thisEMap[eId] = eNum

                    eInDir = f"{editionInDir}/{eId}"
                    eOutDir = f"{editionOutDir}/{eNum}"
                    goodEdition, cEdition, dEdition = dirUpdate(
                        eInDir, eOutDir
                    )
                    c += cEdition
                    d += dEdition
                    writeJson(dict(id=eId), asFile=f"{editionOutDir}/{eNum}/id.json")

                eMap[pId] = thisEMap

            report = f"{c:>3} copied, {d:>3} deleted"
            console(f"{'updated':<10} {'data':<12} {report:<24} to {filesOutDir}")
            return goodOuter and goodProject

        def copyStaticFolder(kind):
            srcDir = locations[kind]
            dstDir = f"{dataOutDir}/{kind}"
            (good, c, d) = dirUpdate(srcDir, dstDir)
            report = f"{c:>3} copied, {d:>3} deleted"
            console(f"{'updated':<10} {kind:<12} {report:<24} to {dstDir}")
            return good

        def registerPartials():
            good = True

            for partialFile in dirAllFiles(partialsIn):
                pDir = dirNm(partialFile).replace(partialsIn, "").strip("/")
                pFile = baseNm(partialFile)
                pName = stripExt(pFile)
                sep = "" if pDir == "" else "/"
                partial = f"{pDir}{sep}{pName}"

                with open(partialFile) as fh:
                    pContent = COMMENT_RE.sub("", fh.read())

                try:
                    partials[partial] = Handlebars.compile(pContent)
                except Exception as e:
                    console(f"{partial} : {str(e)}")
                    good = False

            report = f"{len(partials):<3} pieces"
            console(f"{'compiled':<10} {'partials':<12} {report:<24} to memory")
            return good

        def genCss():
            return T.generate()

        def genTarget(target):
            data = self.getData(target)
            templateFile = f"{templateDir}/{data.template}"

            with open(templateFile) as fh:
                tContent = COMMENT_RE.sub("", fh.read())

            try:
                template = Handlebars.compile(tContent)
                result = template(data, partials=partials)
                path = f"{dataOutDir}/{data.file_name}"

                with open(path, "w") as fh:
                    fh.write(result)

            except Exception as e:
                console(f"{templateFile} : {str(e)}")
                return False

            report = f"{'1':>3} file"
            console(f"{'generated':<10} {target:<12} {report:<24} to {path}")
            return True

        good = True

        if not copyFromExport():
            good = False

        for kind in ("js", "images"):
            if not copyStaticFolder(kind):
                good = False

        if not registerPartials():
            good = False

        if not genCss():
            good = False

        self.getRawData()

        for target in ("site",):
            if not genTarget(target):
                good = False

        if good:
            console("All tasks successful")
        else:
            console("Some tasks failed", error=True)
        return good

    def build(self):
        return self.generate()


def main():
    B = Build()
    result = B.build()
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
