import sys
import re
from copy import deepcopy

from pybars import Compiler
from markdown import markdown

from files import (
    dirContents,
    dirUpdate,
    dirNm,
    dirMake,
    baseNm,
    stripExt,
    abspath,
    writeYaml,
    readYaml,
    readJson,
    writeJson,
    initTree,
    dirAllFiles,
    expanduser as ex,
)
from generic import AttrDict, deepAttrDict, deepdict
from helpers import console, prettify, dottedKey, genViewerSelector
from tailwind import Tailwind


COMMENT_RE = re.compile(r"""\{\{!--.*?--}}""", re.S)

CONFIG_FILE = "config.yaml"
FEATURED_FILE = "featured.yaml"
TAILWIND_CFG = "tailwind.config.js"


class Build:
    def __init__(self):
        baseDir = dirNm(dirNm(abspath(__file__)))
        localDir = f"{baseDir}/_local"

        cfgFile = f"{baseDir}/{CONFIG_FILE}"
        featuredFile = f"{baseDir}/{FEATURED_FILE}"
        featured = readYaml(asFile=featuredFile)
        cfg = readYaml(asFile=cfgFile)

        self.cfg = cfg
        self.featured = featured

        locations = cfg.locations
        self.locations = locations

        self.markdownKeys = set(cfg.markdown.keys)
        self.listKeys = set(cfg.list.keys)

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
        """Get the raw data contained in the json export from Mongo DB.

        This is the metadata of the site, the projects, and the editions.
        We store them as is in member `rawData`.

        Later we distil page data from this, i.e. the data that is ready to fill
        in the variables of the templates.
        """
        rawData = self.rawData

        locations = self.locations
        dataInDir = locations.dataIn
        dbDir = f"{dataInDir}/db/json"

        for kind in ("site", "project", "edition"):
            rawData[kind] = readJson(asFile=f"{dbDir}/{kind}.json")

    def htmlify(self, info):
        """Translate fields in a dict into html.

        Certain fields will trigger a markdown to html conversion.

        Certain fields will be normalized to lists:
        if the type of such a field is not list, it will be turned into a one-element
        list.

        There will also be generated a field whose name has the string `Comma` appended,
        it will be a comma-separated list of the items in that field.

        Parameters
        ----------
        info: dict
            The input data

        Returns
        -------
        AttrDict
            The resulting data. NB: it is brand-new data which does not share
            any data with the input data. Fields are either transformed from markdown
            to HTML, or copied.
        """
        listKeys = self.listKeys
        markdownKeys = self.markdownKeys

        r = AttrDict()

        for k, v in info.items():
            if k in listKeys:
                if type(v) is not list:
                    v = [v]

                r[f"{k}Comma"] = (
                    ""
                    if len(v) == 0
                    else str(v[0])
                    if len(v) == 1
                    else ", ".join(str(e) for e in v[0:-1]) + f" and {v[-1]}"
                )

            if k in markdownKeys:
                v = (
                    "<br>\n".join(markdown(e) for e in v)
                    if type(v) is list
                    else markdown(v)
                )

            r[k] = v

        return r

    def getData(self, kind):
        """Prepares page data of a certain kind.

        Pages are generated by filling in templates and partials on the basis of
        JSON data. Pages may require several kinds of data.
        For example, the index page needs data to fill in a list of projects
        and editions. Other pages may need the same kind of data.
        So we store the gathered data under the kinds they have been gathered.

        Parameters
        ----------
        kind: string
            The kind of data we need to prepare.

        Returns
        -------
        dict or array
            The data itself.
            It is also stored in the member `data` of this object, under key
            `kind`. It will not be computed twice.
        """
        cfg = self.cfg
        generation = cfg.generation
        rawData = self.rawData
        data = self.data
        pMap = self.pMap
        eMap = self.eMap

        if kind in data:
            return data[kind]

        def get_viewers():
            dataOutDir = cfg.locations.dataOut

            viewerDir = f"{dataOutDir}/viewers"
            viewerSettings = cfg.viewers
            defaultViewer = viewerSettings.default
            defaultVersion = viewerSettings[defaultViewer].defaultVersion

            result = []

            for viewer in dirContents(viewerDir)[1]:
                theseSettings = viewerSettings[viewer] or AttrDict()
                element = theseSettings.element or viewer
                isDefault = viewer == defaultViewer

                result.append(
                    AttrDict(
                        name=viewer,
                        element=element,
                        isDefault=isDefault,
                        versions=[
                            AttrDict(
                                name=version,
                                isDefault=isDefault and version == defaultVersion,
                            )
                            for version in reversed(
                                sorted(
                                    dirContents(f"{viewerDir}/{viewer}")[1],
                                    key=dottedKey,
                                )
                            )
                        ],
                    )
                )

            return result

        def get_textpages():
            textDir = cfg.locations.texts
            textFiles = dirContents(textDir)[0]

            def getLinks(textFile):
                return [
                    dict(text=prettify(t.removesuffix(".html")), link=t)
                    for t in textFiles
                    if t != textFile
                ]

            result = []

            for textFile in textFiles:
                r = AttrDict()
                r.template = "p3d-text.html"
                r.name = prettify(textFile.removesuffix(".html"))
                r["is" + r.name] = True
                r.fileName = textFile
                r.links = getLinks(textFile)

                with open(f"{textDir}/{textFile}") as fh:
                    r.content = fh.read()

                result.append(r)

            return result

        def get_site():
            featured = self.featured
            info = rawData[kind]
            item = info[0]
            dc = self.htmlify(item.dc)

            r = AttrDict()
            r.isHome = True
            r.template = "p3d-home.html"
            r.fileName = "index.html"
            r.name = dc.title
            r.contentdata = dc
            projects = self.getData("project")
            projectsIndex = {str(p.num): p for p in projects}
            projectsFeatured = []

            for p in featured.projects:
                p = str(p)
                if p not in projectsIndex:
                    console(f"WARNING: featured project {p} does not exist")
                    continue

                projectsFeatured.append(projectsIndex[p])

            r.projects = projectsFeatured

            return [r]

        def get_projects():
            r = AttrDict()
            r.isProject = True
            r.name = "All Projects"
            r.template = "p3d-projects.html"
            r.fileName = "projects.html"
            r.projects = self.getData("project")

            return [r]

        def get_editions():
            r = AttrDict()
            r.isEdition = True
            r.name = "All Editions"
            r.template = "p3d-editions.html"
            r.fileName = "editions.html"
            r.editions = self.getData("edition")

            return [r]

        def get_project():
            info = rawData[kind]

            result = []

            for item in info:
                itemId = item._id["$oid"]
                itemNo = pMap.get(itemId, itemId)
                dc = self.htmlify(item.dc)

                r = AttrDict()
                r.name = item.title
                r.num = itemNo
                r.fileName = f"project/{itemNo}/index.html"
                r.description = dc.description
                r.abstract = dc.abstract
                r.subjects = dc.subject
                r.visible = item.isVisible
                result.append(r)

            return result

        def get_edition():
            info = rawData[kind]

            result = []

            for item in info:
                itemId = item._id["$oid"]
                itemProjectId = item.projectId["$oid"]
                itemProjectNo = pMap.get(itemProjectId, itemProjectId)
                itemNo = eMap.get(itemProjectId, {}).get(itemId, itemId)
                dc = self.htmlify(item.dc)

                r = AttrDict()
                r.projectNum = itemProjectNo
                r.projectFileName = f"project/{itemProjectNo}.html"
                r.name = item.title
                r.num = itemNo
                r.fileName = f"project/{itemProjectNo}/edition/{itemNo}/index.html"
                r.abstract = dc.abstract
                r.description = dc.description
                r.subjects = dc.subject
                r.published = item.isPublished
                result.append(r)

            return result

        def get_projectpages():
            pInfo = rawData["project"]
            eInfo = rawData["edition"]

            editionByProject = {}

            for eItem in eInfo:
                pId = eItem.projectId["$oid"]
                editionByProject.setdefault(pId, []).append(eItem)

            result = []

            for pItem in pInfo:
                pId = pItem._id["$oid"]
                pNo = pMap.get(pId, pId)
                pdc = self.htmlify(pItem.dc)
                fileName = f"project/{pNo}/index.html"

                pr = AttrDict()
                pr.template = "p3d-project.html"
                pr.fileName = fileName
                pr.num = pNo
                pr.name = pItem.title
                pr.visible = pItem.isVisible
                pr.contentdata = pdc
                pr.editions = []

                for eItem in editionByProject.get(pId, []):
                    eId = eItem._id["$oid"]
                    eNo = eMap.get(pId, {}).get(eId, eId)
                    edc = self.htmlify(eItem.dc)

                    er = AttrDict()
                    er.projectNum = pNo
                    er.projectFileName = f"project/{pNo}/index.html"
                    er.fileName = f"project/{pNo}/edition/{eNo}/index.html"
                    er.num = eNo
                    er.name = eItem.title
                    er.contentdata = edc
                    er.published = eItem.isPublished

                    pr.editions.append(er)

                result.append(pr)

            return result

        def get_editionpages():
            viewers = self.getData("viewers")
            viewersLean = tuple(
                (
                    vw.name,
                    vw.isDefault,
                    tuple((vv.name, vv.isDefault) for vv in vw.versions),
                )
                for vw in viewers
            )

            pInfo = rawData["project"]
            eInfo = rawData["edition"]

            editionByProject = {}

            for eItem in eInfo:
                pId = eItem.projectId["$oid"]
                editionByProject.setdefault(pId, []).append(eItem)

            result = []

            for pItem in pInfo:
                pId = pItem._id["$oid"]
                pNo = pMap.get(pId, pId)
                projectFileName = f"project/{pNo}/index.html"
                projectName = pItem.get("title", pNo)

                for eItem in editionByProject.get(pId, []):
                    eId = eItem._id["$oid"]
                    eNo = eMap.get(pId, {}).get(eId, eId)
                    edc = self.htmlify(eItem.dc)

                    er = AttrDict()
                    er.template = "p3d-edition.html"
                    er.projectNum = pNo
                    er.projectName = projectName
                    er.projectFileName = projectFileName
                    fileBase = f"project/{pNo}/edition/{eNo}/index"
                    er.num = eNo
                    er.name = eItem.title
                    er.contentdata = edc
                    er.isPublished = eItem.ispublished
                    settings = eItem.settings
                    authorTool = settings.authorTool
                    origViewer = authorTool.name
                    origVersion = authorTool.name
                    er.sceneFile = authorTool.sceneFile

                    for viewerInfo in viewers:
                        viewer = viewerInfo.name
                        element = viewerInfo.element
                        versions = viewerInfo.versions
                        isDefaultViewer = viewerInfo.isDefault

                        for versionInfo in versions:
                            version = versionInfo.name
                            isDefault = versionInfo.isDefault
                            ver = deepAttrDict(deepcopy(deepdict(er)))
                            ver.viewer = viewer
                            ver.version = version
                            ver.element = element
                            ver.fileName = f"{fileBase}-{viewer}-{version}.html"
                            isDefault = isDefaultViewer and isDefault

                            viewerSelector = genViewerSelector(
                                viewersLean,
                                viewer,
                                version,
                                origViewer,
                                origVersion,
                                fileBase,
                            )

                            ver.viewerSelector = viewerSelector
                            result.append(ver)

                            if isDefault:
                                ver = deepAttrDict(deepcopy(deepdict(ver)))
                                ver.fileName = f"{fileBase}.html"
                                result.append(ver)

            return result

        getFunc = locals().get(f"get_{kind}", None)

        result = getFunc() if getFunc is not None else []

        data[kind] = result
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
        yamlOutDir = f"{dataOutDir}/yaml"
        Handlebars = self.Handlebars
        partialsIn = locations.partialsIn
        T = self.T

        partials = {}
        compiledTemplates = {}

        def copyFromExport():
            """Copies the export data files to the static file area.

            The copy is incremental at the levels of projects and editions.

            That means: projects and editions will not be removed from the static file
            area.

            So if your export contains a single or a few projects and editions,
            they will be used to update the static file area without affecting material
            of the static file area that is outside these projects and editions.
            """

            goodOuter, cOuter, dOuter = dirUpdate(
                filesInDir, filesOutDir, recursive=False
            )
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
                    goodEdition, cEdition, dEdition = dirUpdate(eInDir, eOutDir)
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
            """Generate the CSS by means of tailwind."""
            return T.generate()

        def genTarget(target):
            items = self.getData(target)

            success = 0
            failure = 0
            good = True

            for item in items:
                templateFile = f"{templateDir}/{item.template}"

                if templateFile in compiledTemplates:
                    template = compiledTemplates[templateFile]
                else:
                    with open(templateFile) as fh:
                        tContent = COMMENT_RE.sub("", fh.read())

                    try:
                        template = Handlebars.compile(tContent)
                    except Exception as e:
                        console(f"{templateFile} : {str(e)}", error=True)
                        template = None

                    compiledTemplates[templateFile] = template

                if template is None:
                    failure += 1
                    good = False
                    continue

                try:
                    result = template(item, partials=partials)
                except Exception as e:
                    console(f"Template = {item.template}")
                    console(f"Item = {item}")
                    console(str(e))
                    failure += 1
                    good = False
                    continue

                for genDir, asYaml in ((dataOutDir, False), (yamlOutDir, True)):
                    path = f"{genDir}/{item.fileName}"
                    if asYaml:
                        path = path.rsplit(".", 1)[0] + ".yaml"
                    dirPart = dirNm(path)
                    dirMake(dirPart)

                    if asYaml:
                        writeYaml(deepdict(item), asFile=path)
                    else:
                        with open(path, "w") as fh:
                            fh.write(result)

                success += 1

            goodStr = f"{success:>3} ok"
            badStr = f"{failure:>3} XX" if failure else ""
            sep = ";" if failure else " "
            report = f"{goodStr}{sep} {badStr}"
            console(f"{'generated':<10} {target:<12} {report:<24} to {dataOutDir}")
            return good

        good = True

        if not copyFromExport():
            good = False

        for kind in ("js", "images", "viewers"):
            if not copyStaticFolder(kind):
                good = False

        if not registerPartials():
            good = False

        if not genCss():
            good = False

        self.getRawData()

        for target in """
            site
            textpages
            projects
            editions
            projectpages
            editionpages
        """.strip().split():
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
