"""Convierte el tarifario de la clínica a CONFIGURACION_DEL_NEGOCIO.xlsx.

Mapeo aplicado (documentado, sin adivinar):
- Tipo Consulta/Procedimiento/Servicio-tratamiento -> kind servicio;
  Producto -> kind producto (sólo BLANQ-002).
- Precio decimal USD -> centavos enteros (35.00 -> 3500).
- Profesional (nombre) -> profesional_codigo; correos operativos FICTICIOS
  (@example.invalid): reemplazar por los reales antes de producción.
- Activos: Luis Mendoza, Ana Torres, Carlos Ramírez (elegidos por el
  propietario). Sofía Rivera y María González se importan inactivas.
- Vigencia 1/1/2026-31/12/2026 -> valid_from/valid_until ISO.
- Unidades 0 en servicios: no aplica (se omite, sin stock).

Uso: .\\.venv-op\\Scripts\\python.exe scripts/convertir_tarifario_clinica.py
Genera CONFIGURACION-clinica.xlsx en la raíz (revíselo antes de importarlo).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm import comercio_excel as xl  # noqa: E402

PROFS = [
    ['LM', 'Dr. Luis Mendoza', 'General', 'luis.mendoza@example.invalid', 1, 'Dr. Luis', 'Odontólogo'],
    ['AT', 'Dra. Ana Torres', 'General', 'ana.torres@example.invalid', 1, 'Dra. Ana', 'Odontóloga'],
    ['CR', 'Dr. Carlos Ramírez', 'General', 'carlos.ramirez@example.invalid', 1, 'Dr. Carlos', 'Odontólogo'],
    ['SR', 'Dra. Sofía Rivera', 'General', 'sofia.rivera@example.invalid', 0, 'Dra. Sofía', 'Odontóloga'],
    ['MG', 'Dra. María González', 'General', 'maria.gonzalez@example.invalid', 0, 'Dra. María', 'Odontóloga'],
]

# (codigo, nombre, detalles, precio_cents, duracion, profesional)
SERVICIOS = [
    ('CONS-001', 'Consulta General', 'Evaluación completa de salud bucal, revisión de encías, dientes y tejidos blandos. Incluye diagnóstico inicial.', 3500, 30, 'LM'),
    ('CONS-002', 'Consulta de Urgencia', 'Atención prioritaria para dolor agudo, traumatismos o emergencias dentales. Evaluación y tratamiento inmediato.', 5000, 45, 'AT'),
    ('CONS-003', 'Valoración Ortodóncica', 'Evaluación especializada para tratamiento de ortodoncia. Análisis de oclusión, espacio y plan de brackets.', 4500, 40, 'CR'),
    ('CONS-004', 'Primera Visita Odontopediatría', 'Primera consulta para niños. Evaluación dental, consejos de higiene y adaptación al consultorio.', 4000, 35, 'SR'),
    ('LIMP-001', 'Limpieza Dental Profunda (Profilaxis)', 'Eliminación de placa y sarro con ultrasonido. Pulido dental y aplicación de flúor. Recomendada cada 6 meses.', 6500, 60, 'MG'),
    ('LIMP-002', 'Limpieza Dental Básica', 'Remoción de placa bacteriana y manchas superficiales. Pulido y fluorización básica.', 4500, 45, 'LM'),
    ('OBTU-001', 'Resina Compuesta (1 cara)', 'Restauración estética con resina del color del diente. Para caries pequeñas o medianas. Acabado y pulido incluido.', 5500, 45, 'AT'),
    ('OBTU-002', 'Resina Compuesta (2-3 caras)', 'Restauración estética para caries extensas. Reconstrucción anatómica completa con resina de alta resistencia.', 7500, 60, 'CR'),
    ('OBTU-003', 'Ionómero de Vidrio', 'Restauración con material que libera flúor. Ideal para zonas de difícil aislamiento o alto riesgo de caries.', 4500, 40, 'SR'),
    ('ENDO-001', 'Tratamiento de Conducto (1 conducto)', 'Endodoncia en dientes anteriores. Eliminación de nervio infectado, limpieza y obturación del conducto radicular.', 18000, 90, 'LM'),
    ('ENDO-002', 'Tratamiento de Conducto (2-3 conductos)', 'Endodoncia en premolares. Tratamiento completo de conductos múltiples con técnica rotatoria y sellado hermético.', 25000, 120, 'MG'),
    ('ENDO-003', 'Tratamiento de Conducto (4 conductos)', 'Endodoncia en molares. Procedimiento complejo en dientes multi-radiculares. Incluye radiografías de control.', 32000, 150, 'CR'),
    ('EXTR-001', 'Extracción Simple', 'Extracción de diente con raíz visible y accesible. Anestesia local, extracción y control post-operatorio.', 6000, 30, 'AT'),
    ('EXTR-002', 'Extracción Compleja (Muela del juicio)', 'Extracción quirúrgica de terceros molares incluidos o semi-incluidos. Incluye sutura y medicación.', 15000, 60, 'LM'),
    ('EXTR-003', 'Extracción de Raíz Remanente', 'Extracción de restos radiculares. Procedimiento quirúrgico menor con anestesia local.', 8000, 45, 'SR'),
    ('PERIO-001', 'Raspado y Alisado Radicular (1 cuadrante)', 'Limpieza profunda bajo la encía para eliminar bacterias y sarro subgingival en enfermedad periodontal.', 12000, 60, 'MG'),
    ('PERIO-002', 'Cirugía de Colgajo Periodontal', 'Cirugía para acceso directo a raíces en enfermedad periodontal avanzada. Regeneración ósea si es necesaria.', 28000, 90, 'CR'),
    ('BLANQ-001', 'Blanqueamiento Dental en Consultorio (LED)', 'Blanqueamiento profesional con gel activado por luz LED. Resultados inmediatos. Incluye kit de mantenimiento.', 25000, 90, 'AT'),
]

PRODUCTOS = [
    ['BLANQ-002', 'Blanqueamiento con Férulas (Domicilio)', 'Férulas personalizadas más gel blanqueador para uso en casa durante 2 semanas. Instrucciones incluidas.', 18000, 'USD', 25, 1],
]


def main() -> int:
    hojas = [
        ('NEGOCIO', [['clave', 'valor'], ['nombre', 'Clínica Demo'], ['zona', 'America/Guayaquil'],
                     ['moneda', 'USD'], ['saludo', 'Hola, gracias por escribirnos.'], ['trato', 'tu']]),
        ('PROFESIONALES', [['codigo', 'nombre', 'especialidad', 'email', 'activo',
                            'publico_nombre', 'publico_rol']] + PROFS),
        ('SERVICIOS', [['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'duracion_min',
                        'profesional_codigo', 'activo', 'vigencia_desde', 'vigencia_hasta']] +
                       [[c, n, d, p, 'USD', m, pr, 1, '2026-01-01', '2026-12-31']
                        for c, n, d, p, m, pr in SERVICIOS]),
        ('PRODUCTOS', [['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'stock', 'activo',
                        'vigencia_desde', 'vigencia_hasta']] +
                      [r + ['2026-01-01', '2026-12-31'] for r in PRODUCTOS]),
        ('PROFESIONAL_SERVICIO', [['servicio_codigo', 'profesional_codigo']] +
                                 [[c, pr] for c, _, _, _, _, pr in SERVICIOS]),
    ]
    data = xl._libro(hojas)
    destino = ROOT / 'CONFIGURACION-clinica.xlsx'
    destino.write_bytes(data)
    print('Archivo:', destino, '(%d bytes)' % len(data))
    print('ADVERTENCIA: los correos @example.invalid son ficticios; reemplazar por los operativos.')
    print('Inactivos: SR (CONS-004, OBTU-003, EXTR-003) y MG (LIMP-001, ENDO-002, PERIO-001):')
    print('esos servicios dirán "no hay profesional disponible" hasta reasignarlos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
