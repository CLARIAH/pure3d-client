const fs = require("fs-extra")
let markdown = require("markdown").markdown
//markdown.toHTML(text)

const myArgs = process.argv.slice(2)
const folderName = myArgs[0]

let path = require("./path.json")
let siteData = require("./" + folderName + "/db/json/site.json")
let projectData = require("./" + folderName + "/db/json/project.json")
let editionData = require("./" + folderName + "/db/json/edition.json")
let aboutData = require("./temp_files/content.json")
let newSite = []

// convert markdown
editionData.forEach(edi => {
  edi.dc.abstract = markdown.toHTML(edi.dc.abstract)
  if (!edi.dc.description === undefined) {
    edi.dc.description = markdown.toHTML(edi.dc.description)
  }
  if (!edi.dc.provenance === undefined) {
    edi.dc.provenance = markdown.toHTML(edi.dc.provenance)
  }
})

projectData.forEach(pr => {
  pr.dc.abstract = markdown.toHTML(pr.dc.abstract)
  if (!pr.dc.description === undefined) {
    pr.dc.description = markdown.toHTML(pr.dc.description)
  }
  if (!pr.dc.provenance === undefined) {
    pr.dc.provenance = markdown.toHTML(pr.dc.provenance)
  }
})

// all projects
let allProjectPages = []
projectData.forEach(projectItem => {
  allProjectPages.push({
    peName: projectItem.title,
    prId: projectItem["_id"]["$oid"],
    peLink: "project_" + saveName(projectItem.title) + ".html",
    peDescription: projectItem.dc.description,
    peAbstract: projectItem.dc.abstract,
    peVisible: projectItem.isVisible,
    peSubjects: projectItem.dc.subject,
    isTypeProject: true,
  })
})

// all editions

let allEditions = []
editionData.forEach(editionItem => {
  allEditions.push({
    peName: editionItem.title,
    edId: editionItem["_id"]["$oid"],
    peLink: "edition_" + saveName(editionItem.title) + ".html",
    peDescription: editionItem.dc.description,
    peAbstract: editionItem.dc.abstract,
    peIsVisible: editionItem.isVisible,
    peSubjects: editionItem.dc.subject,
    isTypeEdition: true,
    prId: editionItem["projectId"]["$oid"],
  })
})

// homepage

newSite.push({
  template: "p3d-home.html",
  title: siteData[0].dc.title,
  file_name: "index.html",
  contentdata: siteData[0].dc,
  projects: allProjectPages,
  editions: allEditions,
})

// All projects
newSite.push({
  template: "p3d-all-projects.html",
  title: "Pure3D projects",
  file_name: "all-projects.html",
  projects: allProjectPages,
  isTypeProject: true,
})

// All Editions
newSite.push({
  template: "p3d-all-projects.html",
  title: "Pure3D Editions",
  file_name: "all-editions.html",
  editions: allEditions,
  isTypeEdition: true,
})

// project pages
projectData.forEach((elem, index) => {
  let pId = elem["_id"]["$oid"]
  let pTitle = elem.title
  let tempPage = {
    template: "",
    title: "",
    file_name: "",
    contentdata: {},
    editions: [],
    subjects: "",
    creator: "",
  }

  tempPage.template = "p3d-project.html"
  tempPage.title = pTitle
  tempPage.file_name = "project_" + saveName(pTitle) + ".html"
  tempPage.contentdata = elem.dc

  editionData.forEach(element => {
    if (elem["_id"]["$oid"] == element["projectId"]["$oid"]) {
      tempPage.filename = "edition_" + saveName(element.title) + ".html"
      tempPage.editionId = element["_id"]["$oid"]
      tempPage.projectId = element["projectId"]["$oid"]
      tempPage.editions.push(element)
    }
  })
  newSite.push(tempPage)
})

// edition pages

editionData.forEach((editionItem, index) => {
  let eId = editionItem["_id"]["$oid"]
  let pId = editionItem["projectId"]["$oid"]
  let pTitle = editionItem.title
  let tempEditionPage = {
    template: "",
    title: "",
    file_name: "",
    contentdata: {},
    project: {},
    projectId: "",
    editionId: "",
    isPublished: "",
    settings: {},
  }

  tempEditionPage.template = "p3d-edition.html"
  tempEditionPage.title = pTitle
  tempEditionPage.file_name = "edition_" + saveName(pTitle) + ".html"
  tempEditionPage.contentdata = editionItem.dc
  tempEditionPage.projectId = pId
  tempEditionPage.editionId = eId
  tempEditionPage.isPublished = editionItem.isPublished
  tempEditionPage.settings = editionItem.settings

  projectData.forEach(projectItem => {
    if (projectItem["_id"]["$oid"] == editionItem["projectId"]["$oid"]) {
      projectItem.projectName = projectItem.title
      projectItem.projectLink = "project_" + saveName(projectItem.title) + ".html"
      tempEditionPage.project = projectItem
    }
  })
  newSite.push(tempEditionPage)
})

newSite.push({
  template: "p3d-text.html",
  title: "About PURE 3D",
  file_name: "about.html",
  contentdata: {
    contentMd: markdown.toHTML(aboutData.content_about),
  },
})

newSite.push({
  template: "p3d-text.html",
  title: "Call for Projects",
  file_name: "call_for_projects.html",
  contentdata: {
    contentMd: markdown.toHTML(aboutData.content_call),
  },
})

//console.log( newSite );

createFile(path.localPath + "/site-p3d.json", JSON.stringify(newSite))

function saveName(str) {
  str = str.replaceAll(" ", "-")
  str = str.replaceAll("&", "")
  str = str.replaceAll(":", "")
  str = str.replaceAll("?", "")
  str = str.replaceAll("\n", "")
  return str.toLowerCase()
}

// create new files
function createFile(fileName, content) {
  fs.writeFile(fileName, content, function (err) {
    if (err) throw err
  })
}
