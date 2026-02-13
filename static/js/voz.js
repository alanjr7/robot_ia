// ===============================
// WEBSOCKET CONNECTION
// ===============================
const socket = io();

// ===============================
// ESTADOS
// ===============================
let estado = "idle"; // idle | escuchando | pensando | hablando
let idiomaActual = "es";

// ===============================
// TEMPORIZADOR IDLE
// ===============================
let temporizadorInactividad;
const tiempoEspera = 8000; // 8s

// ===============================
// WEBSOCKET EVENTS
// ===============================

socket.on('connect', () => {
    console.log(' Conectado al backend de audio');
    console.log(' Esperando estado inicial del backend...');
});

socket.on('status', (data) => {
    console.log(' Status:', data.message);
});

// Evento adicional para debugging del estado
socket.on('state_changed', (data) => {
    console.log(' Estado backend cambiado a:', data.state);
    // Mapear estados del backend al frontend
    const estadoMap = {
        'idle': 'idle',
        'escuchando': 'escuchando', 
        'pensando': 'pensando',
        'hablando': 'hablando'
    };
    estado = estadoMap[data.state] || 'idle';
    console.log(' Estado frontend actualizado a:', estado);
    
    // Activar idle solo cuando el backend dice que está escuchando
    if (estado === 'escuchando') {
        activarIdle();
    }
});

// Evento para actualizar idioma cuando se detecta
socket.on('idioma_detectado', (data) => {
    console.log(' Idioma detectado:', data.idioma);
    idiomaActual = data.idioma;
    console.log(' Idioma actualizado inmediatamente a:', idiomaActual);
});

socket.on('wake_word_detected', (data) => {
    console.log('Wake word detectada:', data.texto);
    clearTimeout(temporizadorInactividad);
    // El estado se actualiza via state_changed, no aquí
    cambiarGesto("sospecha");
});

socket.on('ia_response', (data) => {
    console.log(' Respuesta IA:', data);
    cambiarGesto(data.gesto || "lado");
    idiomaActual = data.idioma || "es";
    console.log(' Idioma actualizado a:', idiomaActual);
    // El estado se actualiza via state_changed, no aquí
});

socket.on('speaking_done', () => {
    console.log(' Terminó de hablar');
    // El estado se actualiza via state_changed, no aquí
});

// ===============================
// FUNCIONES DE UI
// ===============================

function activarIdle() {
    clearTimeout(temporizadorInactividad);
    
    console.log(' Activando temporizador de inactividad - Estado actual:', estado);
    console.log(' Tiempo de espera:', tiempoEspera + 'ms');

    temporizadorInactividad = setTimeout(() => {
        console.log(' Temporizador ejecutado - Verificando estado...');
        console.log(' Estado actual vs requerido:', estado, '!== "escuchando"');
        
        if (estado !== "escuchando") {
            console.log(' No se envía idle_speak - estado no es escuchando');
            return;
        }

        console.log('💤 Enviando idle_speak con idioma:', idiomaActual);
        socket.emit('idle_speak', {
            idioma: idiomaActual
        });

    }, tiempoEspera);
}

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

// ===============================
// INICIO
// ===============================
function iniciar() {
    const overlay = document.getElementById("overlay-inicio");
    if (overlay) overlay.style.display = "none";

    // Notificar al backend que estamos listos para escuchar
    socket.emit('start_listening');
    
    console.log(" Sistema iniciado - Backend de audio activo");
}

// ===============================
// MANEJO DE DESCONEXIÓN
// ===============================
window.addEventListener('beforeunload', () => {
    socket.emit('stop_listening');
    socket.disconnect();
});
