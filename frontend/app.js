// No build step, no frameworks -- plain DOM manipulation is enough for this
// single-page upload/result flow, and keeps the project easy to read.

const form = document.getElementById("analyze-form");
const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".tab-panel");
const textInput = document.getElementById("text-input");
const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const dropZoneText = document.getElementById("drop-zone-text");
const noteInput = document.getElementById("note-input");
const submitBtn = document.getElementById("submit-btn");
const formError = document.getElementById("form-error");

const loadingSection = document.getElementById("loading");
const resultSection = document.getElementById("result");
const formCard = form.closest(".card");

const verdictBadge = document.getElementById("verdict-badge");
const verdictSummary = document.getElementById("verdict-summary");
const redFlagsWrap = document.getElementById("red-flags-wrap");
const redFlagsList = document.getElementById("red-flags-list");
const sourcesWrap = document.getElementById("sources-wrap");
const sourcesList = document.getElementById("sources-list");
const imageWrap = document.getElementById("image-wrap");
const warningImage = document.getElementById("warning-image");
const downloadLink = document.getElementById("download-link");
const resetBtn = document.getElementById("reset-btn");

let activeTab = "text";

const LABEL_TEXT = {
  legitimate: "Looks legitimate",
  likely_fake: "Likely fake",
  scam: "Likely a scam",
  uncertain: "Uncertain — not enough evidence",
};

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    activeTab = tab.dataset.tab;
    tabs.forEach((t) => {
      const isActive = t === tab;
      t.classList.toggle("active", isActive);
      t.setAttribute("aria-selected", String(isActive));
    });
    panels.forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.panel !== activeTab);
    });
    hideError();
  });
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("drag-over");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("drag-over");
  if (event.dataTransfer.files.length > 0) {
    fileInput.files = event.dataTransfer.files;
    updateDropZoneLabel();
  }
});

fileInput.addEventListener("change", updateDropZoneLabel);

function updateDropZoneLabel() {
  const file = fileInput.files[0];
  dropZoneText.textContent = file ? `Selected: ${file.name}` : "Drag and drop, or click to choose a file (max 20 MB)";
}

function showError(message) {
  formError.textContent = message;
  formError.classList.remove("hidden");
}

function hideError() {
  formError.classList.add("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();

  const text = textInput.value.trim();
  const file = fileInput.files[0];

  if (activeTab === "text" && !text) {
    showError("Paste a message or link first.");
    return;
  }
  if (activeTab === "file" && !file) {
    showError("Choose an image or video first.");
    return;
  }

  const formData = new FormData();
  if (activeTab === "text") {
    formData.append("text", text);
  } else {
    formData.append("file", file);
  }
  if (noteInput.value.trim()) {
    formData.append("note", noteInput.value.trim());
  }

  setLoading(true);

  try {
    const response = await fetch("/api/analyze", { method: "POST", body: formData });
    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      const message = (payload && payload.detail) || `Request failed (${response.status}).`;
      throw new Error(message);
    }

    renderResult(payload);
  } catch (error) {
    showError(error.message || "Something went wrong. Please try again.");
    setLoading(false);
  }
});

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  loadingSection.classList.toggle("hidden", !isLoading);
  if (isLoading) {
    formCard.classList.add("hidden");
    resultSection.classList.add("hidden");
  }
}

function renderResult(payload) {
  setLoading(false);
  resultSection.classList.remove("hidden");

  const verdict = payload.verdict;
  verdictBadge.textContent = `${LABEL_TEXT[verdict.label] || verdict.label} (${Math.round(verdict.confidence * 100)}% confidence)`;
  verdictBadge.className = `badge ${verdict.label}`;
  verdictSummary.textContent = verdict.summary;

  redFlagsList.innerHTML = "";
  if (verdict.red_flags && verdict.red_flags.length > 0) {
    verdict.red_flags.forEach((flag) => {
      const li = document.createElement("li");
      li.textContent = flag;
      redFlagsList.appendChild(li);
    });
    redFlagsWrap.classList.remove("hidden");
  } else {
    redFlagsWrap.classList.add("hidden");
  }

  sourcesList.innerHTML = "";
  if (verdict.sources && verdict.sources.length > 0) {
    verdict.sources.forEach((source) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = source.url;
      a.textContent = source.title;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.appendChild(a);
      li.appendChild(document.createTextNode(` — ${source.note}`));
      sourcesList.appendChild(li);
    });
    sourcesWrap.classList.remove("hidden");
  } else {
    sourcesWrap.classList.add("hidden");
  }

  if (payload.warning_image_url) {
    warningImage.src = payload.warning_image_url;
    downloadLink.href = payload.warning_image_url;
    imageWrap.classList.remove("hidden");
  } else {
    imageWrap.classList.add("hidden");
  }
}

resetBtn.addEventListener("click", () => {
  form.reset();
  updateDropZoneLabel();
  resultSection.classList.add("hidden");
  formCard.classList.remove("hidden");
  hideError();
});
