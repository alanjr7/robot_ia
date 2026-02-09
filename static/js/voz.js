// ===============================
// SPEECH RECOGNITION SETUP
// ===============================
const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

const recognition = new SpeechRecognition();
recognition.lang = "es-BO";
recognition.continuous = true;
recognition.interimResults = false;

// ===============================
// ESTADOS
// idle | escuchando | pensando | hablando
// ===============================
let estado = "idle";

// ===============================
// IDLE
// ===============================
let temporizadorInactividad;
const tiempoEspera = 18000; // 18s

const frasesRandom = [
    { mensaje: "Hola, sigo trabajando.", gesto: "lado" },
    { mensaje: "Entregar comida me gusta.", gesto: "feliz" },
    { mensaje: "Todo está tranquilo.", gesto: "lado" },
    { mensaje: "Un paso a la vez.", gesto: "lado" },
    { mensaje: "Estoy aquí para ayudar.", gesto: "feliz" },
    { mensaje: "Espero que estés bien.", gesto: "feliz" },
    { mensaje: "Algo se siente raro.", gesto: "sospecha" }
];

// ===============================
// VOZ
// ===============================
let vocesDisponibles = [];
let vozPreferida = null;

function cargarVoces() {
    vocesDisponibles = speechSynthesis.getVoices();

    vozPreferida =
        vocesDisponibles.find(v => v.name.toLowerCase().includes("sofia")) ||
        vocesDisponibles.find(v => v.lang === "es-BO") ||
        vocesDisponibles.find(v => v.lang === "es-MX") ||
        vocesDisponibles.find(v => v.lang.includes("es"));
}

speechSynthesis.onvoiceschanged = cargarVoces;

// ===============================
// HELPERS
// ===============================
function iniciarEscucha() {
    try {
        recognition.start();
    } catch (_) {}
}

function detenerEscucha() {
    try {
        recognition.stop();
    } catch (_) {}
}

function activarIdle() {
    clearTimeout(temporizadorInactividad);

    temporizadorInactividad = setTimeout(() => {
        if (estado !== "escuchando") return;

        estado = "hablando";
        const accion =
            frasesRandom[Math.floor(Math.random() * frasesRandom.length)];

        detenerEscucha();
        cambiarGesto(accion.gesto);
        hablar(accion.mensaje);
    }, tiempoEspera);
}

// ===============================
// INICIO
// ===============================
function iniciar() {
    cargarVoces();

    const overlay = document.getElementById("overlay-inicio");
    if (overlay) overlay.style.display = "none";

    estado = "escuchando";
    iniciarEscucha();
    activarIdle();

    console.log("Sistema iniciado");
}

// ===============================
// ESCUCHA
// ===============================
recognition.onresult = async (event) => {
    if (estado !== "escuchando") return;

    activarIdle();

    const ultimo = event.results[event.results.length - 1];
    const texto = ultimo[0].transcript.toLowerCase().trim();

    console.log("Escuchado:", texto);

    const esWakeWord = /\b(dinner|diner)\b/.test(texto);
    if (!esWakeWord) return;

    estado = "pensando";
    detenerEscucha();
    cambiarGesto("sospecha");

    try {
        const res = await fetch("/procesar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto })
        });

        const data = await res.json();

        estado = "hablando";
        cambiarGesto(data.gesto || "lado");
        hablar(data.mensaje || "Hola...");

    } catch (e) {
        console.error("Error API:", e);
        estado = "escuchando";
        iniciarEscucha();
        activarIdle();
    }
};

// ===============================
// MANTENER ESCUCHA
// ===============================
recognition.onend = () => {
    if (estado === "escuchando") {
        iniciarEscucha();
    }
};

recognition.onerror = (e) => {
    console.error("Speech error:", e.error);
    if (estado === "escuchando") {
        setTimeout(iniciarEscucha, 1000);
    }
};

// ===============================
// HABLAR
// ===============================
function hablar(texto) {
    detenerEscucha();

    const utterance = new SpeechSynthesisUtterance(texto);

    if (vozPreferida) {
        utterance.voice = vozPreferida;
        utterance.lang = vozPreferida.lang;
    } else {
        utterance.lang = "es-MX";
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.1;

    utterance.onend = () => {
        estado = "escuchando";
        iniciarEscucha();
        activarIdle();
    };

    speechSynthesis.speak(utterance);
}

// ===============================
// GESTOS
// ===============================
function cambiarGesto(gesto) {
    const video = document.getElementById("robot");
    if (!video) return;

    if (!video.src.includes(gesto)) {
        video.src = `/static/videos/${gesto}.mp4`;
        video.loop = (gesto === "lado");
        video.play().catch(() => {});
    }

    if (gesto !== "lado") {
        setTimeout(() => {
            if (estado !== "hablando") {
                video.src = "/static/videos/lado.mp4";
                video.loop = true;
                video.play().catch(() => {});
            }
        }, 4000);
    }
}
