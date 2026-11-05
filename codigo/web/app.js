"use strict";

const MAX_ESPERA_INTENTOS = 900; // 30 minutos, con sondeo cada 2 segundos

function $(id) {
  return document.getElementById(id);
}

async function pedir(ruta, opciones) {
  const respuesta = await fetch(ruta, opciones);
  let datos = {};
  try {
    datos = await respuesta.json();
  } catch (_) {
    datos = {};
  }
  return { ok: respuesta.ok, status: respuesta.status, datos: datos };
}

function mostrarEstado(texto) {
  $("estado").textContent = texto;
}

function mostrarFuentes(cambios) {
  const caja = $("alerta");
  const lista = $("alerta-lista");
  lista.textContent = "";
  if (!cambios || cambios.length === 0) {
    caja.style.display = "none";
    return;
  }
  $("alerta-titulo").textContent = "Hay fuentes distintas a las de la última corrida. Recalcule el mes afectado para validarlo.";
  for (const cambio of cambios) {
    const elemento = document.createElement("li");
    elemento.textContent = cambio.archivo + " (" + cambio.estado + ")";
    lista.appendChild(elemento);
  }
  caja.style.display = "block";
}

async function cargarMeses() {
  const select = $("mes");
  const anterior = select.value;
  select.textContent = "";
  const cargando = document.createElement("option");
  cargando.textContent = "Cargando meses...";
  select.appendChild(cargando);
  const respuesta = await pedir("/api/meses");
  select.textContent = "";
  if (!respuesta.ok) {
    mostrarEstado(respuesta.datos.mensaje || "No se pudieron leer los meses.");
    return;
  }
  for (const mes of respuesta.datos.meses) {
    const opcion = document.createElement("option");
    opcion.value = mes;
    opcion.textContent = mes;
    select.appendChild(opcion);
  }
  const eleccion = respuesta.datos.meses.includes(anterior) ? anterior : respuesta.datos.seleccionado;
  if (eleccion) {
    select.value = eleccion;
  }
}

async function cargarUltima() {
  const respuesta = await pedir("/api/corridas/ultima");
  if (!respuesta.ok) {
    $("vista").removeAttribute("src");
    $("info").textContent = respuesta.datos.mensaje || "";
    return;
  }
  $("vista").src = respuesta.datos.dashboard;
  $("info").textContent = "Corrida " + respuesta.datos.id + " · Período " + respuesta.datos.periodo + " · Generada " + respuesta.datos.generado;
}

async function cargarEstado() {
  const respuesta = await pedir("/api/estado");
  if (respuesta.ok) {
    mostrarFuentes(respuesta.datos.fuentes_cambiadas);
    return respuesta.datos.actualizacion || {};
  }
  return {};
}

async function esperarFin() {
  let estado = {};
  for (let intento = 0; intento < MAX_ESPERA_INTENTOS; intento++) {
    await new Promise((resolver) => setTimeout(resolver, 2000));
    estado = await cargarEstado();
    if (estado.estado !== "en_curso") {
      break;
    }
    mostrarEstado("Calculando " + (estado.periodo || "") + "...");
  }
  return estado;
}

async function actualizar() {
  const boton = $("actualizar");
  const periodo = $("mes").value;
  boton.disabled = true;
  const respuesta = await pedir("/api/actualizar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ periodo: periodo }),
  });
  if (respuesta.status !== 202) {
    mostrarEstado(respuesta.datos.mensaje || "No se pudo iniciar la actualización.");
    boton.disabled = false;
    return;
  }
  mostrarEstado("Calculando " + periodo + "...");
  const estado = await esperarFin();
  boton.disabled = false;
  if (estado.estado === "completada") {
    mostrarEstado("Listo: " + estado.periodo + " calculado.");
    await cargarMeses();
    await cargarUltima();
  } else {
    mostrarEstado("Error: " + (estado.error || "el cálculo no terminó.") + " Se conserva la vista anterior.");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  $("actualizar").addEventListener("click", actualizar);
  await Promise.all([cargarMeses(), cargarUltima()]);
  const estado = await cargarEstado();
  if (estado.estado === "en_curso") {
    $("actualizar").disabled = true;
    const final = await esperarFin();
    $("actualizar").disabled = false;
    if (final.estado === "completada") {
      await cargarMeses();
      await cargarUltima();
    }
  }
});
