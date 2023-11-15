const handlebars = require("handlebars")
const fs = require("fs-extra")
const path = require("path")

const beautify = require("beautify")

const myArgs = process.argv.slice(2)
const projct = myArgs[0]

const sitedata = require(`../${projct}/data/site-${projct}.json`)
const partialsDir = `./${projct}/components/`

const dataInDir = `/Users/me/local/pure3d/client/input`
const dataOutDir = `/Users/me/local/pure3d/client/dist`

build()

function build() {
  fs.remove(dataOutDir)
    .then(createFolder)
    .then(registerPartials)
    .then(generateHtml)
    .then(copyFiles)
    .then(copyDist)
    .catch(err => {
      console.error(err)
    })
}

// register partials (components) and generate site files
function registerPartials() {
  return new Promise((resolve, reject) => {
    const longPath = path.resolve(partialsDir)
    const walk = (dir, done) => {
      let results = []
      fs.readdir(dir, (err, list) => {
        if (err) {
          return done(err)
        }
        let pending = list.length
        if (!pending) {
          return done(null, results)
        }
        list.forEach(fl => {
          let file = path.resolve(dir, fl)
          fs.stat(file, (err, stat) => {
            // if dir
            if (stat && stat.isDirectory()) {
              walk(file, (err, res) => {
                results = results.concat(res)
                if (!--pending) {
                  done(null, results)
                }
              })
            } else {
              results.push(file.replace(`${longPath}/`, ""))
              file = file.replace(`${longPath}/`, "")

              fs.readFile(`${projct}/components/${file}`, "utf-8", (error, source) => {
                handlebars.registerPartial(file.replace(path.extname(file), ""), source)
              })
              if (!--pending) {
                done(null, results)
              }
            }
          })
        })
      })
    }

    walk(partialsDir, (err, results) => {
      if (err) {
        throw err
      }
      setTimeout(() => {
        resolve(results)
      }, 500)
    })
  })
}

// generate files
function generateHtml() {
  sitedata.forEach(item => {
    fs.readFile(`${projct}/templates/${item.template}`, "utf-8", (error, source) => {
      const template = handlebars.compile(source)
      let html = template(item)
      html = beautify(html, { format: "html" })
      createFile(`${dataOutDir}/${item.file_name}`, html)
    })
  })
}

// create new files
function createFile(fileName, content) {
  fs.writeFile(fileName, content, err => {
    if (err) {
      throw err
    }
  })
}

// create folders
function createFolder() {
  fs.mkdirSync(dataOutDir)
  fs.mkdirSync(`${dataOutDir}/images`)
  fs.mkdirSync(`${dataOutDir}/js`)
}

function copyFiles() {
  fs.cp(`./${projct}/images/`, `${dataOutDir}/images/`, { recursive: true }, err => {
    if (err) {
      console.error(err)
    }
  })

  fs.cp(`./${projct}/js/`, `${dataOutDir}/js/`, { recursive: true }, err => {
    if (err) {
      console.error(err)
    }
  })

  if (fs.existsSync(dataInDir)) {
    fs.cp(dataInDir, `${dataOutDir}/`, { recursive: true }, err => {
      if (err) {
        console.error(err)
      }
    })
  }
}

function saveName(str) {
  return str
    .replaceAll(" ", "-")
    .str.replaceAll("&", "")
    .str.replaceAll(":", "")
    .str.replaceAll("?", "")
    .str.replaceAll("\n", "")
    .str.toLowerCase()
}

function copyDist() {
  const copyfolderPath = `${projct}/data/copy_folder.json`
  if (fs.existsSync(`./${copyfolderPath}`)) {
    const copyPath = require(`../${copyfolderPath}`)
    setTimeout(() => {
      fs.cp(dataOutDir, copyPath[0], { recursive: true }, err => {
        if (err) {
          console.error(err)
        }
      })
    }, 1000)
  }
}
