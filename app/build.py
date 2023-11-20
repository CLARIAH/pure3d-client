import sys
import re

from pybars import Compiler

from files import (
    fileCopy,
    dirNm,
    baseNm,
    stripExt,
    abspath,
    readYaml,
    readJson,
    initTree,
    dirContents,
    dirAllFiles,
    expanduser as ex,
)
from helpers import console
from tailwind import Tailwind


COMMENT_RE = re.compile(r"""\{\{!--.*?--}}""", re.S)

CONFIG_FILE = "config.yaml"
TAILWIND_CFG = "tailwind.config.js"


class Build:
    def __init__(self):
        baseDir = dirNm(dirNm(abspath(__file__)))
        self.baseDir = baseDir
        localDir = f"{baseDir}/_local"
        self.localDir = localDir

        cfgFile = f"{baseDir}/{CONFIG_FILE}"
        cfg = readYaml(asFile=cfgFile)
        self.cfg = cfg

        locations = cfg.locations
        self.locations = locations

        for k, v in locations.items():
            v = v.replace("«base»", baseDir)
            locations[k] = ex(v)

        outDir = locations.dataOut

        self.Handlebars = Compiler()

        initTree(locations.dataIn, fresh=False)

        T = Tailwind(baseDir, localDir, TAILWIND_CFG, outDir)
        T.install()
        self.tailwindBin = T.binPath

    def getData(self, target):
        locations = self.locations
        dataInDir = locations.dataIn
        dbDir = f"{dataInDir}/db/json"
        # fileDir = f"{dataInDir}/files"

        if target == "index":
            result = readJson(asFile=f"{dbDir}/site.json")[0]
            result.template = "p3d-home.html"
            result.file_name = "index.html"
            dc = result.dc
            result.title = dc.title
            result.contentdata = dc

        return result

    def registerPartials(self):
        locations = self.locations
        partialsIn = locations.partialsIn
        Handlebars = self.Handlebars

        partials = {}

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

        self.partials = partials
        print(f"{len(partials)} partials compiled")

    def generate(self):
        locations = self.locations
        dataInDir = locations.dataIn
        filesDir = f"{dataInDir}/files"
        templateDir = locations.templates
        outDir = locations.dataOut
        Handlebars = self.Handlebars
        partials = self.partials

        initTree(outDir, fresh=True, gentle=False)

        def genTarget(target):
            data = self.getData(target)
            templateFile = f"{templateDir}/{data.template}"

            if target == "index":
                for file in dirContents(filesDir)[0]:
                    fileCopy(f"{filesDir}/{file}", f"{outDir}/{file}")
                    pass

            with open(templateFile) as fh:
                tContent = COMMENT_RE.sub("", fh.read())

            try:
                template = Handlebars.compile(tContent)
                result = template(data, partials=partials)
                path = f"{outDir}/{data.file_name}"

                with open(path, "w") as fh:
                    fh.write(result)
                console(f"{target} generated in {path}")

            except Exception as e:
                console(f"{templateFile} : {str(e)}")

        for target in ("index",):
            genTarget(target)

    def build(self):
        self.registerPartials()
        self.generate()
        return True


def main():
    B = Build()
    result = B.build()
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
