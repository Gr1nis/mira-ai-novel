/**
 * Визуальная новелла «Мира» — Логика фронтенда (app.js)
 */
document.addEventListener("DOMContentLoaded", () => {
  // DOM Элементы
  const portraitImg = document.getElementById("characterPortrait");
  const emotionBadge = document.getElementById("activeEmotionBadge");
  const emotionLabel = document.getElementById("emotionLabelText");
  const chatFeed = document.getElementById("chatFeed");
  const chatForm = document.getElementById("chatForm");
  const messageInput = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const thinkingIndicator = document.getElementById("thinkingIndicator");
  const alertBanner = document.getElementById("alertBanner");
  const alertMessage = document.getElementById("alertMessage");
  const btnCloseAlert = document.getElementById("btnCloseAlert");
  const btnResetHistory = document.getElementById("btnResetHistory");
  
  // Модальное окно настроек
  const btnSettings = document.getElementById("btnSettings");
  const settingsModal = document.getElementById("settingsModal");
  const btnCloseSettings = document.getElementById("btnCloseSettings");
  const btnSaveSettings = document.getElementById("btnSaveSettings");
  const inputBaseUrl = document.getElementById("settingBaseUrl");
  const inputModel = document.getElementById("settingModel");
  const inputApiKey = document.getElementById("settingApiKey");
  const checkSimMode = document.getElementById("settingSimulationMode");

  // Восстановление настроек из LocalStorage
  const savedBaseUrl = localStorage.getItem("mira_base_url");
  const savedModel = localStorage.getItem("mira_model");
  const savedApiKey = localStorage.getItem("mira_api_key");
  const savedSimMode = localStorage.getItem("mira_sim_mode");

  if (savedBaseUrl) inputBaseUrl.value = savedBaseUrl;
  if (savedModel) inputModel.value = savedModel;
  if (savedApiKey) inputApiKey.value = savedApiKey;
  if (savedSimMode !== null) checkSimMode.checked = (savedSimMode === "true");

  function saveSettingsToStorage() {
    localStorage.setItem("mira_base_url", inputBaseUrl.value.trim());
    localStorage.setItem("mira_model", inputModel.value.trim());
    localStorage.setItem("mira_api_key", inputApiKey.value.trim());
    localStorage.setItem("mira_sim_mode", checkSimMode.checked);
  }

  // Состояние
  let history = [];
  let currentEmotion = "neutral";
  let isThinking = false;

  const EMOTION_MAP = {
    neutral: { label: "neutral (спокойствие)", class: "badge-neutral" },
    joy: { label: "joy (радость)", class: "badge-joy" },
    sadness: { label: "sadness (грусть)", class: "badge-sadness" },
    anger: { label: "anger (гнев)", class: "badge-anger" },
    fear: { label: "fear (страх)", class: "badge-fear" },
    disgust: { label: "disgust (отвращение)", class: "badge-disgust" },
    surprise: { label: "surprise (удивление)", class: "badge-surprise" }
  };

  // Переключение эмоции персонажа с плавной анимацией
  function setCharacterEmotion(emotion) {
    const validEmotion = EMOTION_MAP[emotion] ? emotion : "neutral";
    currentEmotion = validEmotion;

    portraitImg.classList.add("fade-out");
    setTimeout(() => {
      portraitImg.src = `assets/sprites/${validEmotion}.jpg`;
      portraitImg.onerror = () => {
        portraitImg.src = `assets/sprites/${validEmotion}.svg`;
      };
      portraitImg.onload = () => {
        portraitImg.classList.remove("fade-out");
        portraitImg.classList.add("fade-in");
        setTimeout(() => portraitImg.classList.remove("fade-in"), 350);
      };
    }, 150);

    // Обновляем бейдж
    emotionBadge.className = `emotion-badge ${EMOTION_MAP[validEmotion].class}`;
    emotionLabel.textContent = EMOTION_MAP[validEmotion].label;
  }

  // Быстрый предпросмотр мимики по клику на чип
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => setCharacterEmotion(chip.dataset.emotion));
  });

  // Добавление сообщения в ленту
  function appendMessage(role, text, emotion = null) {
    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role === "user" ? "user" : "mira"}`;

    if (role === "assistant") {
      const header = document.createElement("div");
      header.className = "mira-header";
      header.innerHTML = `<span>Мира</span>`;
      if (emotion && EMOTION_MAP[emotion]) {
        const tag = document.createElement("span");
        tag.className = `mira-emotion-tag ${EMOTION_MAP[emotion].class}`;
        tag.textContent = emotion;
        header.appendChild(tag);
      }
      bubble.appendChild(header);
    }

    const content = document.createElement("div");
    content.textContent = text;
    bubble.appendChild(content);

    chatFeed.appendChild(bubble);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  function showAlert(msg) {
    alertMessage.textContent = msg;
    alertBanner.classList.remove("hidden");
  }

  function hideAlert() {
    alertBanner.classList.add("hidden");
  }

  btnCloseAlert.addEventListener("click", hideAlert);

  // Очистка истории
  btnResetHistory.addEventListener("click", () => {
    history = [];
    chatFeed.innerHTML = `
      <div class="message-bubble system-note">
        <span>🎭 История очищена. Начните новый диалог с Мирой.</span>
      </div>`;
    setCharacterEmotion("neutral");
    hideAlert();
  });

  // Отправка реплики
  async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isThinking) return;

    hideAlert();
    appendMessage("user", text);
    messageInput.value = "";
    messageInput.style.height = "auto";

    isThinking = true;
    btnSend.disabled = true;
    messageInput.disabled = true;
    thinkingIndicator.classList.remove("hidden");
    chatFeed.scrollTop = chatFeed.scrollHeight;

    // Проверяем демо-режим симуляции
    if (checkSimMode.checked) {
      setTimeout(() => {
        const simulated = getSimulatedResponse(text);
        setCharacterEmotion(simulated.emotion);
        appendMessage("assistant", simulated.reply, simulated.emotion);
        history.push({ role: "user", content: text });
        history.push({ role: "assistant", content: simulated.reply });
        finishThinking();
      }, 700);
      return;
    }

    try {
      const payload = {
        message: text,
        history: history,
        base_url: inputBaseUrl.value.trim(),
        model: inputModel.value.trim(),
        api_key: inputApiKey.value.trim(),
        temperature: 0.7
      };

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "Ошибка запроса" }));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      history = data.history || [];
      setCharacterEmotion(data.emotion);
      appendMessage("assistant", data.reply, data.emotion);

      if (data.fallback_applied) {
        console.warn("Fallback notice:", data.error_detail);
      }

    } catch (err) {
      console.error(err);
      setCharacterEmotion("neutral");
      showAlert(`Не удалось связаться с моделью: ${err.message}. Проверьте статус Ollama или включите автономный демо-режим в Настройках.`);
    } finally {
      finishThinking();
    }
  }

  function finishThinking() {
    isThinking = false;
    btnSend.disabled = false;
    messageInput.disabled = false;
    thinkingIndicator.classList.add("hidden");
    messageInput.focus();
  }

  // Офлайн демо-эмуляция реплик Миры строго по характеру (Приложение А)
  function getSimulatedResponse(userText) {
    const lower = userText.toLowerCase();
    if (lower.includes("привет") || lower.includes("здравствуй") || lower.includes("рад") || lower.includes("кофе")) {
      return { emotion: "joy", reply: "Привет! Да нормально, пью крепкий кофе, за окном стучит дождь." };
    } else if (lower.includes("груст") || lower.includes("устал") || lower.includes("уволил") || lower.includes("работу") || lower.includes("один") || lower.includes("жаль")) {
      return { emotion: "sadness", reply: "Ох... Мне правда жаль. Хочешь рассказать, что стряслось?" };
    } else if (lower.includes("надоел") || lower.includes("замолчи") || lower.includes("дур") || lower.includes("глуп") || lower.includes("ужасн")) {
      return { emotion: "anger", reply: "Зачем так грубо? Я ведь ничего плохого тебе не сделала." };
    } else if (lower.includes("монстр") || lower.includes("подвал") || lower.includes("темно") || lower.includes("страш") || lower.includes("опасн")) {
      return { emotion: "fear", reply: "Т-ты серьёзно? Не пугай меня так, мне уже не по себе..." };
    } else if (lower.includes("ананас") || lower.includes("таракан") || lower.includes("грязь") || lower.includes("фу")) {
      return { emotion: "disgust", reply: "Фу... Это просто преступление против хорошего вкуса." };
    } else if (lower.includes("выиграл") || lower.includes("миллион") || lower.includes("лотере") || lower.includes("нло") || lower.includes("чудо")) {
      return { emotion: "surprise", reply: "Что?! Серьёзно?! Не разыгрываешь меня? Рассказывай скорей!" };
    }
    return { emotion: "joy", reply: "Интересно... В этом есть что-то поэтичное, как в новой картине." };
  }

  // Обработка клавиш Enter / Shift+Enter
  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage();
  });

  // Модалка настроек
  btnSettings.addEventListener("click", () => settingsModal.classList.remove("hidden"));
  btnCloseSettings.addEventListener("click", () => settingsModal.classList.add("hidden"));
  btnSaveSettings.addEventListener("click", () => {
    saveSettingsToStorage();
    settingsModal.classList.add("hidden");
  });
  settingsModal.querySelector(".modal-backdrop").addEventListener("click", () => settingsModal.classList.add("hidden"));
});
