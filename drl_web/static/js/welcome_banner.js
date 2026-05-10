(() => {
  const openButton = document.querySelector("[data-welcome-open]")
  const overlay = document.querySelector("[data-welcome-overlay]")
  const panel = document.getElementById("welcome-banner")
  const closeButton = document.querySelector("[data-welcome-close]")

  if (!openButton || !overlay || !panel || !closeButton) {
    return
  }

  let lastFocused = null

  const openWelcome = () => {
    lastFocused = document.activeElement
    overlay.hidden = false
    document.body.classList.add("welcome-open")
    panel.focus()
  }

  const closeWelcome = () => {
    overlay.hidden = true
    document.body.classList.remove("welcome-open")
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus()
    }
  }

  openButton.addEventListener("click", openWelcome)
  closeButton.addEventListener("click", closeWelcome)
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      closeWelcome()
    }
  })
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !overlay.hidden) {
      closeWelcome()
    }
  })
})()
