function voyagerVersion(page) {
  const embed = document.getElementById("viewer3d")

  const e = document.getElementById("v_version")
  const version = e.value
  embed.setAttribute("resourceroot", `data/viewers/voyager/${version}`)
  document.getElementById("viewer3d").outerHTML = embed.outerHTML
  console.log("set2")

  //window.location.href = '/' + page + '?v=' + version;
}

function getParameterByName(name, url = window.location.href) {
  const newName = name.replace(/[[\]]/g, "\\$&")
  const regex = new RegExp(`[?&]${newName}(=([^&#]*)|&|#|$)`),
    results = regex.exec(url)
  if (!results) {
    return null
  }
  if (!results[2]) {
    return ""
  }
  return decodeURIComponent(results[2].replace(/\+/g, " "))
}
