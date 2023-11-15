import sys
import re

from pybars import Compiler

from files import (
    dirNm,
    baseNm,
    stripExt,
    abspath,
    readYaml,
    initTree,
    dirAllFiles,
    expanduser as ex,
)


COMMENT_RE = re.compile(r"""\{\{!--.*?--}}""", re.S)

CONFIG_FILE = "config.yaml"


class Build:
    def __init__(self):
        baseDir = dirNm(dirNm(abspath(__file__)))
        self.baseDir = baseDir

        cfgFile = f"{baseDir}/{CONFIG_FILE}"
        cfg = readYaml(asFile=cfgFile)
        self.cfg = cfg

        locations = cfg.locations
        self.locations = locations

        for k, v in locations.items():
            v = v.replace("«base»", baseDir)
            locations[k] = ex(v)

        self.Handlebars = Compiler()

        initTree(locations.dataIn, fresh=False)

    def registerPartials(self):
        baseDir = self.baseDir
        locations = self.locations
        partialsIn = locations.partialsIn
        Handlebars = self.Handlebars

        partials = {}

        for partialFile in dirAllFiles(partialsIn):
            pDir = dirNm(partialFile).replace(baseDir, "").strip("/")
            pFile = baseNm(partialFile)
            pName = stripExt(pFile)

            with open(partialFile) as fh:
                pContent = COMMENT_RE.sub("", fh.read())

            try:
                partials[pName] = Handlebars.compile(pContent)
            except Exception as e:
                print(f"{pDir} / {pName}: {str(e)}")

        self.partials = partials
        print(f"{len(partials)} partials compiled")

    def generate(self):
        locations = self.locations

        initTree(locations.dataOut, fresh=True, gentle=False)

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
