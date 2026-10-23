"""Aplicacion Streamlit para la administracion de la clinica dental."""

import sqlite3
from typing import Any, Dict, List

import streamlit as st
from database.models import Tratamiento
from database.db_manager import GestorDB


CSS_EMERGENCIA = """
<style>
@keyframes parpadeo-rojo {
    0%, 100% { background-color: #ff0000; box-shadow: 0 0 20px #ff0000; }
    50% { background-color: #990000; box-shadow: 0 0 5px #990000; }
}
.alarma-emergencia {
    animation: parpadeo-rojo 1s infinite;
    color: white;
    padding: 15px 25px;
    border-radius: 10px;
    font-size: 20px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 15px;
}
.fila-emergencia {
    background-color: #fff0f0 !important;
    border-left: 5px solid #ff0000 !important;
}
</style>
"""


def inicializar_aplicacion() -> GestorDB:
    """Configura la pagina de Streamlit y retorna un GestorDB."""
    st.set_page_config(
        page_title="Panel de Administracion - Clinica Dental",
        layout="wide",
    )
    gestor = GestorDB(ruta_bd="clinica.db")
    gestor.inicializar_tablas()
    return gestor


def mostrar_pestania_tratamientos(
    gestor: GestorDB,
) -> None:
    """Renderiza la pestania de gestion de tratamientos."""
    st.header("Gestion de Tratamientos")

    col_formulario, col_listado = st.columns(2)

    with col_formulario:
        st.subheader("Nuevo Tratamiento")
        with st.form("form_tratamiento", clear_on_submit=True):
            nombre = st.text_input("Nombre")
            precio = st.number_input(
                "Precio",
                min_value=0.0,
                step=0.01,
                format="%.2f",
            )
            requisitos = st.text_area("Requisitos")
            enviado = st.form_submit_button("Agregar Tratamiento")

        if enviado:
            try:
                if not nombre.strip():
                    st.error("El nombre del tratamiento no puede estar vacio.")
                else:
                    tratamiento = Tratamiento(
                        nombre=nombre.strip(),
                        precio=precio,
                        requisitos=requisitos.strip(),
                    )
                    gestor.agregar_tratamiento(tratamiento)
                    st.success("Tratamiento agregado correctamente.")
                    st.rerun()
            except (sqlite3.Error, ValueError) as e:
                st.error(f"Error al agregar tratamiento: {e}")

    with col_listado:
        st.subheader("Catalogo de Tratamientos")
        try:
            tratamientos = gestor.obtener_tratamientos()
            if not tratamientos:
                st.info("El catalogo de tratamientos esta vacio.")
            else:
                data: List[Dict[str, Any]] = [
                    {
                        "ID": t.id,
                        "Nombre": t.nombre,
                        "Precio": f"${t.precio:.2f}",
                        "Requisitos": t.requisitos,
                    }
                    for t in tratamientos
                ]
                st.dataframe(data, use_container_width=True)
        except (sqlite3.Error, ValueError) as e:
            st.error(f"Error al cargar tratamientos: {e}")


def mostrar_pestania_citas(
    gestor: GestorDB,
) -> None:
    """Renderiza la pestana de visor de citas."""
    st.header("Visor de Citas")

    try:
        citas = gestor.obtener_todas_las_citas()
        if not citas:
            st.info("No hay citas registradas.")
        else:
            data: List[Dict[str, Any]] = [
                {
                    "ID": c.id,
                    "Telefono": c.paciente_telefono,
                    "Fecha y Hora": c.fecha_hora,
                    "Estado": c.estado,
                }
                for c in citas
            ]
            st.dataframe(data, use_container_width=True)
    except (sqlite3.Error, ValueError) as e:
        st.error(f"Error al cargar citas: {e}")


def mostrar_pestania_emergencias(
    gestor: GestorDB,
) -> None:
    """Renderiza la pestana de emergencias con alarma visual."""
    st.markdown(CSS_EMERGENCIA, unsafe_allow_html=True)
    st.header("Emergencias - Revision Manual")

    try:
        emergencias_pendientes = gestor.obtener_emergencias_pendientes()
        todas_emergencias = gestor.obtener_todas_las_emergencias()

        if emergencias_pendientes:
            st.markdown(
                f'<div class="alarma-emergencia">'
                f"🚨 {len(emergencias_pendientes)} EMERGENCIA(S) PENDIENTE(S) "
                f"- COMUNICARSE CON EL PACIENTE 🚨</div>",
                unsafe_allow_html=True,
            )

        st.subheader("Emergencias Pendientes")
        if not emergencias_pendientes:
            st.success("No hay emergencias pendientes. Todo en orden.")
        else:
            for em in emergencias_pendientes:
                with st.container():
                    col_info, col_accion = st.columns([3, 1])
                    with col_info:
                        nombre = em.paciente_nombre or "Sin nombre"
                        st.markdown(
                            f"**🔴 Telefono:** {em.paciente_telefono}  |  "
                            f"**Nombre:** {nombre}"
                        )
                        st.markdown(f"**Mensaje:** {em.mensaje_emergencia}")
                        st.caption(f"Registrado: {em.fecha_registro}")
                    with col_accion:
                        if st.button(
                            "Marcar Atendida",
                            key=f"atendida_{em.id}",
                        ):
                            gestor.actualizar_estado_emergencia(em.id, "atendida")
                            st.rerun()
                    st.divider()

        st.subheader("Historial de Emergencias")
        if not todas_emergencias:
            st.info("No hay emergencias registradas.")
        else:
            data: List[Dict[str, Any]] = [
                {
                    "ID": e.id,
                    "Telefono": e.paciente_telefono,
                    "Nombre": e.paciente_nombre or "-",
                    "Mensaje": e.mensaje_emergencia,
                    "Fecha": e.fecha_registro,
                    "Estado": e.estado.upper(),
                }
                for e in todas_emergencias
            ]
            st.dataframe(data, use_container_width=True)

    except (sqlite3.Error, ValueError) as e:
        st.error(f"Error al cargar emergencias: {e}")


def main() -> None:
    """Punto de entrada principal de la aplicacion."""
    gestor = inicializar_aplicacion()

    pestanas = ["Gestion de Tratamientos", "Visor de Citas", "🚨 Emergencias"]
    tab_tratamientos, tab_citas, tab_emergencias = st.tabs(pestanas)

    with tab_tratamientos:
        mostrar_pestania_tratamientos(gestor)

    with tab_citas:
        mostrar_pestania_citas(gestor)

    with tab_emergencias:
        mostrar_pestania_emergencias(gestor)


if __name__ == "__main__":
    main()
