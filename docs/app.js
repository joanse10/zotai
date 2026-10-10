/* ==========================================================================
   Zotai - Landing & Download Client Logic
   Multi-language engine, interactive tabs, copy-to-clipboard, modal
   ========================================================================== */

// Translations dictionary
const translations = {
  ro: {
    navFeatures: "Funcționalități",
    navPipeline: "Arhitectură",
    navDownloads: "Descărcare",
    navDocs: "Ghid CLI",
    navFaq: "FAQ",
    heroBadge: "Versiunea 1.1.0 lansată • Open Source Apache 2.0",
    heroTitle: "Catalogare bibliografică automată cu AI pentru Zotero",
    heroSubtitle: "Transformă orice fișier PDF sau DOCX într-o fișă bibliografică completă. Extrage text nativ sau scanează prin OCR, preia metadate din baze online și îmbogățește automat câmpurile lipsă cu AI.",
    btnDownloadWin: "Descarcă pentru Windows",
    btnPortable: "Versiune Portabilă (.zip)",
    btnGithub: "Vezi pe GitHub",
    sysReq: "Windows 10 / 11 (64-bit) • ~48 MB • Inno Setup",
    
    // Preview Mockup
    mockTitle: "Zotai v1.1.0 - Catalogare Bibliografică",
    mockBadge: "Zotero Conectat (23119)",
    mockSearchPlaceholder: "Căutare după DOI, ISBN, titlu sau URL...",
    mockAddBtn: "+ Adaugă Fișiere",
    mockColFile: "Fișier / Titlu",
    mockColStatus: "Stare",
    mockColType: "Tip",
    mockColYear: "An",
    mockStatusDone: "Sincronizat",
    mockStatusProcessing: "Extragere OCR",
    mockStatusAi: "Completare AI",
    mockInspectorTitle: "Inspector Metadate (XMP/Zotero)",
    mockLblTitle: "Titlu Document",
    mockLblAuthors: "Autori",
    mockLblDoi: "Identificator DOI",
    mockLblCzu: "Clasificare CZU / LBC",

    // Downloads
    secDownloadTag: "Instalare & Kit-uri",
    secDownloadTitle: "Alegeți pachetul potrivit",
    secDownloadDesc: "Descărcați fișierele de instalare oficiale verificate cu semnătură SHA-256.",
    cardInstTitle: "Instalator Windows",
    cardInstDesc: "Instalare completă asistată cu meniu contextual, comandă rapidă și asistent în limba română.",
    cardPortTitle: "Portabil Windows",
    cardPortDesc: "Arhivă ZIP autonomă — dezarhivați și rulați fără privilegii de administrator.",
    cardSourceTitle: "Cod Sursă Python",
    cardSourceDesc: "Pentru dezvoltatori și medii headless. Rulare prin pip și linie de comandă.",
    btnDownload: "Descarcă",
    btnViewChecksum: "Verifică Hash SHA-256",
    
    // Features
    secFeatTag: "Avantaje Cheie",
    secFeatTitle: "De ce Zotai?",
    feat1Title: "Extragere Mixtă Text & OCR",
    feat1Desc: "Citește textul nativ în milisecunde cu PyMuPDF sau trece pe Tesseract OCR automat când documentul este scanat.",
    feat2Title: "Metadate Hibride & AI CLI",
    feat2Desc: "Identifică DOI/ISBN din text pentru date exacte (CrossRef, OpenLibrary) și folosește AI CLI doar pentru câmpurile goale.",
    feat3Title: "Injectare Directă în Fișier",
    feat3Desc: "Scrie metadatele direct în PDF (XMP Dublin Core/PRISM) și DOCX cu generare automată de backup *.xmpbak.",
    feat4Title: "Coadă Offline (Zero Data Loss)",
    feat4Desc: "Dacă Zotero este închis, sarcinile sunt păstrate în siguranță în SQLite și trimise automat la redeschidere.",
    feat5Title: "100% Multilingv & Dinamic",
    feat5Desc: "Interfață modulară cu fișiere externe JSON (Română, Rusă, Engleză) — poți adăuga limbi noi fără să modifici codul.",
    feat6Title: "Complet Open-Source & Privat",
    feat6Desc: "Toate datele rămân pe calculatorul tău. Fără telemetrie ascunsă, licențiat liber sub Apache 2.0.",

    // FAQ
    faqTitle: "Întrebări Frecvente",
    faq1Q: "Zotai funcționează dacă Zotero este oprit?",
    faq1A: "Da. Zotai procesează fișierele, injectează metadatele XMP și le salvează în baza de date locală SQLite. Când deschideți Zotero, articolele se sincronizează automat pe portul 23119.",
    faq2Q: "Ce motoare AI sunt compatibile?",
    faq2A: "Zotai suportă orice asistent CLI configurat: Antigravity agy, Claude Code, Ollama (local) sau comenzi personalizate cu parametri JSON.",
    faq3Q: "Unde sunt stocate datele aplicatiei?",
    faq3A: "Toate setările, baza de date zotai.db și jurnalele se păstrează în %LOCALAPPDATA%\\Zotai și nu se pierd la actualizări sau reinstalări."
  },

  ru: {
    navFeatures: "Возможности",
    navPipeline: "Архитектура",
    navDownloads: "Скачать",
    navDocs: "CLI Документация",
    navFaq: "FAQ",
    heroBadge: "Релиз v1.1.0 • Open Source Apache 2.0",
    heroTitle: "Автоматическая каталогизация с AI для Zotero",
    heroSubtitle: "Превращает любые PDF и DOCX в готовые библиографические записи. Извлекает текст или сканирует через OCR, подтягивает точные метаданные из баз и заполняет пропуски через AI.",
    btnDownloadWin: "Скачать для Windows",
    btnPortable: "Портативная версия (.zip)",
    btnGithub: "Смотреть на GitHub",
    sysReq: "Windows 10 / 11 (64-бит) • ~48 МБ • Inno Setup",

    // Preview Mockup
    mockTitle: "Zotai v1.1.0 - Библиографический Каталогизатор",
    mockBadge: "Zotero Подключён (23119)",
    mockSearchPlaceholder: "Поиск по DOI, ISBN, названию или ссылке на PDF...",
    mockAddBtn: "+ Добавить файлы",
    mockColFile: "Файл / Название",
    mockColStatus: "Статус",
    mockColType: "Тип",
    mockColYear: "Год",
    mockStatusDone: "Синхронизирован",
    mockStatusProcessing: "Распознавание OCR",
    mockStatusAi: "Обогащение AI",
    mockInspectorTitle: "Инспектор метаданных (XMP/Zotero)",
    mockLblTitle: "Название документа",
    mockLblAuthors: "Авторы",
    mockLblDoi: "Идентификатор DOI",
    mockLblCzu: "Индексы УДК / ББК",

    // Downloads
    secDownloadTag: "Установка и Релизы",
    secDownloadTitle: "Выберите подходящий пакет",
    secDownloadDesc: "Загрузите проверенные сборки с контрольными суммами SHA-256.",
    cardInstTitle: "Установщик Windows",
    cardInstDesc: "Полноценная установка с интеграцией в контекстное меню Windows, ярлыком и деинсталлятором.",
    cardPortTitle: "Портативная версия",
    cardPortDesc: "Автономный ZIP-архив — распакуйте в любую папку и запускайте без прав администратора.",
    cardSourceTitle: "Python Исходники",
    cardSourceDesc: "Для разработчиков и серверов. Запуск через pip и командную строку.",
    btnDownload: "Скачать",
    btnViewChecksum: "Показать хеш SHA-256",

    // Features
    secFeatTag: "Преимущества",
    secFeatTitle: "Почему именно Zotai?",
    feat1Title: "Гибридный парсер: Текст + OCR",
    feat1Desc: "Быстро читает цифровой текст через PyMuPDF, а для сканов автоматически запускает Tesseract с загрузкой языков.",
    feat2Title: "Точные API + AI Дополнение",
    feat2Desc: "Находит DOI/ISBN для 100% точности (CrossRef, OpenLibrary), а AI CLI подключается только для пустых полей (ББК/УДК).",
    feat3Title: "Вшивание метаданных в файл",
    feat3Desc: "Записывает XMP Dublin Core/PRISM прямо в тело PDF и DOCX с автоматическим созданием резервной копии *.xmpbak.",
    feat4Title: "Оффлайн-очередь (Zero Data Loss)",
    feat4Desc: "Если Zotero закрыт, задачи надёжно хранятся в SQLite и автоматически отправятся, как только вы его запустите.",
    feat5Title: "Модульная локализация JSON",
    feat5Desc: "Мгновенное переключение языков (румынский, русский, английский) без необходимости перекомпилировать код.",
    feat6Title: "100% Приватно и Open-Source",
    feat6Desc: "Все вычисления на вашем компьютере. Никакой телеметрии, свободная лицензия Apache 2.0.",

    // FAQ
    faqTitle: "Часто задаваемые вопросы",
    faq1Q: "Будет ли работать программа, если Zotero выключен?",
    faq1A: "Да! Zotai обработает файлы, внедрит XMP метаданные и сохранит задачи в SQLite. При следующем запуске Zotero они автоматически синхронизируются через порт 23119.",
    faq2Q: "Какие AI-модели поддерживаются?",
    faq2A: "Любые через CLI-адаптер: Antigravity agy, Claude Code, локальный Ollama или любые кастомные консольные команды с JSON выводом.",
    faq3Q: "Где хранятся пользовательские данные?",
    faq3A: "Вся база данных zotai.db, логи и языковые пакеты хранятся в %LOCALAPPDATA%\\Zotai и не удаляются при обновлениях."
  },

  en: {
    navFeatures: "Features",
    navPipeline: "Architecture",
    navDownloads: "Download",
    navDocs: "CLI Guide",
    navFaq: "FAQ",
    heroBadge: "Version 1.1.0 Released • Open Source Apache 2.0",
    heroTitle: "Automated AI Document Cataloger for Zotero",
    heroSubtitle: "Transform any PDF or DOCX file into complete bibliographic cards. Extracts native text or runs OCR, looks up metadata online, and fills missing fields with AI CLI.",
    btnDownloadWin: "Download for Windows",
    btnPortable: "Portable Version (.zip)",
    btnGithub: "View on GitHub",
    sysReq: "Windows 10 / 11 (64-bit) • ~48 MB • Inno Setup",

    // Preview Mockup
    mockTitle: "Zotai v1.1.0 - Bibliographic Cataloger",
    mockBadge: "Zotero Connected (23119)",
    mockSearchPlaceholder: "Search by DOI, ISBN, title or web PDF URL...",
    mockAddBtn: "+ Add Files",
    mockColFile: "File / Title",
    mockColStatus: "Status",
    mockColType: "Type",
    mockColYear: "Year",
    mockStatusDone: "Synced",
    mockStatusProcessing: "OCR Ingest",
    mockStatusAi: "AI Enrich",
    mockInspectorTitle: "Metadata Inspector (XMP/Zotero)",
    mockLblTitle: "Document Title",
    mockLblAuthors: "Authors",
    mockLblDoi: "DOI Identifier",
    mockLblCzu: "UDC / LBC Classification",

    // Downloads
    secDownloadTag: "Releases & Binaries",
    secDownloadTitle: "Choose your distribution",
    secDownloadDesc: "Official binaries verified with SHA-256 cryptographic hashes.",
    cardInstTitle: "Windows Installer",
    cardInstDesc: "Full setup wizard with Windows context menu integration, desktop shortcut, and clean uninstaller.",
    cardPortTitle: "Windows Portable",
    cardPortDesc: "Self-contained ZIP archive — unpack anywhere and run without administrative privileges.",
    cardSourceTitle: "Python Source Code",
    cardSourceDesc: "For developers and headless servers. Run via pip and standard CLI scripts.",
    btnDownload: "Download",
    btnViewChecksum: "View SHA-256 Hash",

    // Features
    secFeatTag: "Key Features",
    secFeatTitle: "Why Zotai?",
    feat1Title: "Dual Extraction: Native & OCR",
    feat1Desc: "Reads native PDF text in milliseconds with PyMuPDF, or switches to Tesseract OCR when documents are scanned.",
    feat2Title: "Hybrid Online API + AI CLI",
    feat2Desc: "Resolves DOI/ISBN against CrossRef and OpenLibrary for 100% accuracy, using AI only to complete blank fields.",
    feat3Title: "Direct In-File Metadata Injection",
    feat3Desc: "Writes XMP Dublin Core and PRISM metadata into PDF & DOCX with guaranteed *.xmpbak safety backups.",
    feat4Title: "Offline Queue (Zero Data Loss)",
    feat4Desc: "If Zotero is closed, items are safely queued in SQLite WAL and auto-synced the moment Zotero starts up.",
    feat5Title: "Modular Dynamic Translations",
    feat5Desc: "External JSON locales (Romanian, Russian, English) allow adding new languages without touching source code.",
    feat6Title: "100% Private & Open Source",
    feat6Desc: "All data stays on your machine. Zero tracking telemetry, permissive Apache 2.0 license.",

    // FAQ
    faqTitle: "Frequently Asked Questions",
    faq1Q: "Does Zotai work when Zotero is not running?",
    faq1A: "Yes. Zotai extracts text, writes XMP tags, and queues items in its local SQLite database. Once Zotero starts, items auto-sync to port 23119.",
    faq2Q: "Which AI models can be used?",
    faq2A: "Any CLI assistant: Antigravity agy, Claude Code, local Ollama, or any custom command returning JSON schema.",
    faq3Q: "Where is user data saved?",
    faq3A: "The zotai.db database, OCR packs, and logs are kept in %LOCALAPPDATA%\\Zotai and are preserved across reinstalls."
  }
};

let currentLang = 'ro';

function setLanguage(lang) {
  if (!translations[lang]) return;
  currentLang = lang;
  document.documentElement.lang = lang;

  // Update dropdown button text
  const currentLangLabel = document.getElementById('currentLangLabel');
  if (currentLangLabel) {
    const labels = { ro: 'Română', ru: 'Русский', en: 'English' };
    currentLangLabel.textContent = labels[lang] || lang.toUpperCase();
  }

  // Update selected class in dropdown
  document.querySelectorAll('.lang-opt').forEach(opt => {
    opt.classList.toggle('selected', opt.dataset.lang === lang);
  });

  // Apply translations to all data-i18n elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (translations[lang][key]) {
      el.textContent = translations[lang][key];
    }
  });

  // Apply placeholders
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    if (translations[lang][key]) {
      el.placeholder = translations[lang][key];
    }
  });

  localStorage.setItem('zotai_lang', lang);
}

// Interactive Code Tabs
const codeSnippets = {
  run: `# Rulare directă din surse
pip install -r requirements.txt
python main.py`,
  worker: `# Extragere text & OCR pentru un document
python -m worker document.pdf --lang ron+rus+eng --pretty`,
  ocr: `# Gestionare pachete de limbi Tesseract
python -m worker.lang_manager list
python -m worker.lang_manager install ron ukr rus`,
  build: `# Construirea instalatorului binar complet
python -m PyInstaller zotai.spec --noconfirm
iscc installer/zotai.iss`
};

function initCodeTabs() {
  const tabs = document.querySelectorAll('.code-tab');
  const codeDisplay = document.getElementById('codeDisplay');
  if (!codeDisplay) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const snippetKey = tab.dataset.tab;
      if (codeSnippets[snippetKey]) {
        codeDisplay.textContent = codeSnippets[snippetKey];
      }
    });
  });
}

// Copy to Clipboard
function copyToClipboard(text, successMsg) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(successMsg || "Copiat în clipboard!");
  }).catch(() => {
    showToast("Eroare la copiere.");
  });
}

function showToast(message) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2600);
}

// Modal handling for SHA-256 Checksums
function openChecksumModal(filename, hash) {
  const modal = document.getElementById('checksumModal');
  const modalFilename = document.getElementById('modalFilename');
  const modalHash = document.getElementById('modalHash');
  if (!modal) return;

  modalFilename.textContent = filename;
  modalHash.textContent = hash;
  modal.classList.add('active');
}

function closeChecksumModal() {
  const modal = document.getElementById('checksumModal');
  if (modal) modal.classList.remove('active');
}

// FAQ Accordion
function initFaq() {
  document.querySelectorAll('.faq-item').forEach(item => {
    const question = item.querySelector('.faq-question');
    question.addEventListener('click', () => {
      const isActive = item.classList.contains('active');
      document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('active'));
      if (!isActive) item.classList.add('active');
    });
  });
}

// Language dropdown toggle
function initLangSelector() {
  const btn = document.getElementById('langBtn');
  const dropdown = document.getElementById('langDropdown');
  if (!btn || !dropdown) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('active');
  });

  document.addEventListener('click', () => {
    dropdown.classList.remove('active');
  });

  document.querySelectorAll('.lang-opt').forEach(opt => {
    opt.addEventListener('click', () => {
      const lang = opt.dataset.lang;
      setLanguage(lang);
      dropdown.classList.remove('active');
    });
  });
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  // Detect language or use stored
  const savedLang = localStorage.getItem('zotai_lang') || navigator.language.slice(0, 2);
  const initialLang = ['ro', 'ru', 'en'].includes(savedLang) ? savedLang : 'ro';

  initLangSelector();
  setLanguage(initialLang);
  initCodeTabs();
  initFaq();

  // Copy code button
  const copyBtn = document.getElementById('copyCodeBtn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const codeDisplay = document.getElementById('codeDisplay');
      if (codeDisplay) copyToClipboard(codeDisplay.textContent, "Comandă copiată!");
    });
  }

  // Copy modal hash button
  const copyHashBtn = document.getElementById('copyHashBtn');
  if (copyHashBtn) {
    copyHashBtn.addEventListener('click', () => {
      const hashEl = document.getElementById('modalHash');
      if (hashEl) copyToClipboard(hashEl.textContent, "SHA-256 copiat!");
    });
  }

  // Modal close handlers
  const modalClose = document.getElementById('modalClose');
  const modalOverlay = document.getElementById('checksumModal');
  if (modalClose) modalClose.addEventListener('click', closeChecksumModal);
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeChecksumModal();
    });
  }
});
