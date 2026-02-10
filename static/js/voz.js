// ===============================
// SPEECH RECOGNITION SETUP
// ===============================
const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

const recognition = new SpeechRecognition();
recognition.lang = "en-US";
recognition.continuous = true;
recognition.interimResults = false;

// ===============================
// ESTADOS
// idle | escuchando | pensando | hablando
// ===============================
let estado = "idle";
let idiomaActual = "es"; // Guardar el último idioma detectado

// ===============================
// CONTROL FLAGS (OBLIGATORIO)
// ===============================
let recognitionActivo = false;
let speaking = false;

// ===============================
// IDLE
// ===============================
let temporizadorInactividad;
const tiempoEspera = 10000; // 10s

const frasesRandom = [
    { mensaje: { es: "A Dinner le gusta que lo llamen por su nombre. Decí 'Dinner' y te escucho", en: "Dinner likes to be called by name. Say 'Dinner' and I'll listen" }, gesto: "lado" },
    { mensaje: { es: "Regla básica: si no decís 'Dinner', sigo comiendo bits.", en: "Basic rule: if you don't say 'Dinner', I keep eating bits" }, gesto: "sospecha" },
    { mensaje: { es: "¿Querés hablar conmigo? Fácil: decí 'Dinner' primero.", en: "Want to talk to me? Easy: say 'Dinner' first" }, gesto: "feliz" },
    { mensaje: { es: "Estoy en standby… activame diciendo 'Dinner'.", en: "I'm on standby... activate me by saying 'Dinner'" }, gesto: "lado" },
    { mensaje: { es: "Dinner no responde a gritos, solo a su nombre", en: "Dinner doesn't respond to shouts, only to its name" }, gesto: "sospecha" },

    { mensaje: { es: "Escaneando antojos… resultado: TODO. (Después de decir 'Dinner').", en: "Scanning cravings... result: EVERYTHING. (After saying 'Dinner')." }, gesto: "sospecha" },
    { mensaje: { es: "Confirmado: decir 'Dinner' fue una excelente decisión.", en: "Confirmed: saying 'Dinner' was an excellent decision" }, gesto: "feliz" },
    { mensaje: { es: "El hambre no negocia… pero Dinner sí, si lo llamás.", en: "Hunger doesn't negotiate... but Dinner does, if you call it" }, gesto: "lado" },
    { mensaje: { es: "Procesando pedido… activación por palabra clave detectada.", en: "Processing order... keyword activation detected" }, gesto: "sospecha" },
    { mensaje: { es: "Nivel de felicidad subiendo desde que dijiste 'Dinner'.", en: "Happiness level rising since you said 'Dinner'" }, gesto: "feliz" },

    { mensaje: { es: "Comida en camino… wake word correcta, paciencia en cooldown.", en: "Food on the way... correct wake word, patience on cooldown" }, gesto: "lado" },
    { mensaje: { es: "Alerta: decir 'Dinner' puede generar respuestas automáticas.", en: "Alert: saying 'Dinner' may generate automatic responses" }, gesto: "sospecha" },
    { mensaje: { es: "El universo aprueba que llames a Dinner por su nombre.", en: "The universe approves that you call Dinner by its name" }, gesto: "feliz" },
    { mensaje: { es: "Hambre derrotada tras pronunciación correcta de 'Dinner'.", en: "Hunger defeated after correct pronunciation of 'Dinner'" }, gesto: "feliz" },
    { mensaje: { es: "Comer solo es triste… por suerte llamaste a Dinner.", en: "Eating alone is sad... luckily you called Dinner" }, gesto: "lado" }
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
    if (recognitionActivo || speaking) return;

    try {
        recognition.start();
        recognitionActivo = true;
        console.log("🎤 Escuchando...");
    } catch (_) {}
}

function detenerEscucha() {
    if (!recognitionActivo) return;

    try {
        recognition.stop();
        recognitionActivo = false;
        console.log("🛑 Escucha detenida");
    } catch (_) {}
}

function activarIdle() {
    clearTimeout(temporizadorInactividad);

    temporizadorInactividad = setTimeout(() => {
        if (estado !== "escuchando") return;

        estado = "hablando";
        const accion = frasesRandom[Math.floor(Math.random() * frasesRandom.length)];

        detenerEscucha();
        cambiarGesto(accion.gesto);
        
        // Usar el último idioma detectado para las frases aleatorias
        const mensaje = accion.mensaje[idiomaActual] || accion.mensaje.es;
        
        hablar(mensaje);
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

    // Capturar todos los resultados, no solo el último
    let textoCompleto = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
        textoCompleto += event.results[i][0].transcript + " ";
    }
    textoCompleto = textoCompleto.toLowerCase().trim();

    console.log("Escuchado:", textoCompleto);

    // Regex más tolerante sin \b
    const esWakeWord = /(dinner|diner)/i.test(textoCompleto);
    if (!esWakeWord) return;

    estado = "pensando";
    detenerEscucha();
    cambiarGesto("sospecha");

    try {
        const res = await fetch("/procesar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto: textoCompleto })
        });

        const data = await res.json();

        estado = "hablando";
        cambiarGesto(data.gesto || "lado");
        
        // Usar idioma explícito del backend
        idiomaActual = data.idioma || "es";
        
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
    recognitionActivo = false;
    console.log("🎧 Recognition ended");
};

recognition.onerror = (e) => {
    recognitionActivo = false;
    console.warn("Speech error:", e.error);

    if (estado === "escuchando" && !speaking) {
        setTimeout(iniciarEscucha, 800);
    }
};

// ===============================
// HABLAR
// ===============================
function hablar(texto) {
    if (speaking) return;

    speaking = true;
    detenerEscucha();

    const utterance = new SpeechSynthesisUtterance(texto);

    utterance.lang = idiomaActual === "en" ? "en-US" : "es-MX";
    utterance.rate = 1;
    utterance.pitch = 1.1;

    if (vozPreferida) {
        utterance.voice = vozPreferida;
    }

    utterance.onend = () => {
        speaking = false;
        estado = "escuchando";

        setTimeout(() => {
            iniciarEscucha();
            activarIdle();
        }, 300);
    };

    speechSynthesis.cancel(); // 🔥 clave
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
