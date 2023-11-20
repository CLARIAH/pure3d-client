import re
import platform
import stat
import os
import ssl
from urllib.request import urlopen
from shutil import copyfileobj
import certifi
from helpers import console
from files import fileExists


TAILWIND_VERSION = "v3.3.5"

TARGETS = dict(
    amd64="{}-x64",
    x86_64="{}-x64",
    arm64="{}-arm64",
    aarch64="{}-arm64",
)


def detectTarget():
    """Binary targets for tailwind.

    [Available tailwindcss targets](https://github.com/tailwindlabs/tailwindcss/releases)
    """


class Tailwind:
    def __init__(self, baseDir, localDir, configFile, distDir):
        self.baseDir = baseDir
        self.localDir = localDir
        self.configFile = configFile
        self.distDir = distDir

    def install(self):
        baseDir = self.baseDir
        localDir = self.localDir
        configFile = self.configFile
        distDir = self.distDir
        configInPath = f"{baseDir}/{configFile}"
        configOutPath = f"{localDir}/{configFile}"

        osName = platform.system().lower().replace("darwin", "macos")
        assert osName in ["linux", "macos"]
        arch = platform.machine().lower()
        target = TARGETS[arch].format(osName)
        binName = f"tailwindcss-{target}"
        binPath = f"{localDir}/{binName}"
        self.binPath = binPath
        v = (
            "latest/download"
            if TAILWIND_VERSION == "latest"
            else f"download/{TAILWIND_VERSION}"
        )
        url = f"https://github.com/tailwindlabs/tailwindcss/releases/{v}/{binName}"

        if not fileExists(binPath):
            console(f"Downloading {binName} from {url} ...")
            certifi_context = ssl.create_default_context(cafile=certifi.where())

            with urlopen(url, context=certifi_context) as instream, open(
                binPath, "wb"
            ) as outfile:
                copyfileobj(instream, outfile)

            os.chmod(binPath, os.stat(binPath).st_mode | stat.S_IEXEC)
            console("done")

        if True or not fileExists(configOutPath):
            with open(configInPath) as fh:
                text = fh.read()

            contentRe = re.compile(r"""\b(content:\s*\[).*?(\],)""")

            fileSpec = f"{distDir}/**/*." + "{html,js}"

            def contentRepl(match):
                (pre, post) = match.group(1, 2)

                return f"""{pre}"{fileSpec}"{post}"""

            text = contentRe.sub(contentRepl, text)

            with open(configOutPath, "w") as fh:
                fh.write(text)
