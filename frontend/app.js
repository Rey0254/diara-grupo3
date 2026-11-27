
// Proyecto dIAra - Grupo 3
// Carga centralizada de datos

async function cargarDatos() {
    try {
        const respuesta = await fetch("../data/datos_demo.json");

        if (!respuesta.ok) {
            throw new Error("No se pudieron cargar los datos");
        }

        const datos = await respuesta.json();

        window.datosDiara = datos;

        console.log("Datos cargados correctamente:", datos);

        mostrarInformacionObra(datos);

        document.dispatchEvent(
            new CustomEvent("datosDiaraListos", {
                detail: datos
            })
        );

    } catch (error) {
        console.error("Error:", error);

        document.getElementById("info-obra").textContent =
            "No fue posible cargar la información de la obra.";
    }
}

// Información general de la obra

function mostrarInformacionObra(datos) {
    const obra = datos.obra;
    const contenedor = document.getElementById("info-obra");

    const campos = [
        ["Fuente", datos.tipo_datos],
        ["Nombre", obra.nombre],
        ["Ubicación", obra.ubicacion],
        ["Institución responsable", obra.institucion_responsable],
        ["Avance contractual", obra.avance_contractual],
        ["Última actualización", obra.ultima_actualizacion]
    ];

    contenedor.replaceChildren();

    campos.forEach(([etiqueta, valor]) => {
        const parrafo = document.createElement("p");
        const titulo = document.createElement("strong");

        titulo.textContent = etiqueta + ": ";

        parrafo.append(
            titulo,
            String(valor ?? "Información no disponible")
        );

        contenedor.appendChild(parrafo);
    });
}

// Iniciar la aplicación

document.addEventListener("DOMContentLoaded", cargarDatos);
