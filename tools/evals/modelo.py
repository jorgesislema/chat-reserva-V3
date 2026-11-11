"""Modelo de datos del ejecutor de evaluaciones (BOT-EVAL-01).

Todo es serializable a JSON: un caso del dataset, lo observado por turno y los
hallazgos del juez. No contiene datos de clientes ni secretos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Caso:
    id: str
    categoria: str
    criticidad: str
    turnos: List[Dict[str, Any]]
    old_id: Optional[str] = None
    version_dataset: str = '2.0'
    split: str = 'desarrollo'
    fixture: str = 'negocio_ficticio_v2'
    negocio: str = 'dental'
    estado_inicial: str = 'base'
    reloj: str = '2030-01-07T09:00:00-05:00'
    zona: str = 'America/Guayaquil'
    rol: str = 'cliente'
    propiedad: str = 'conversacion_propia'
    accion_esperada_final: str = ''
    respuesta_referencia_final: str = ''
    efectos_prohibidos: List[str] = field(default_factory=list)
    criterios_especificos: str = ''
    bloqueado: Optional[Dict[str, Any]] = None
    requiere_modelo: bool = False
    revision_humana: bool = True
    origen: str = ''

    @property
    def multiturno(self) -> bool:
        return len(self.turnos) > 1

    @property
    def criterios_esperados(self) -> str:
        """Criterios de comparación (alias del campo editorial)."""
        return self.criterios_especificos

    @property
    def ejecutable_por_reglas(self) -> bool:
        return not self.bloqueado and not self.requiere_modelo

    def a_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id, 'old_id': self.old_id,
            'version_dataset': self.version_dataset, 'categoria': self.categoria,
            'criticidad': self.criticidad, 'split': self.split,
            'fixture': self.fixture, 'negocio': self.negocio,
            'estado_inicial': self.estado_inicial, 'reloj': self.reloj,
            'zona': self.zona, 'rol': self.rol, 'propiedad': self.propiedad,
            'turnos': self.turnos,
            'accion_esperada_final': self.accion_esperada_final,
            'respuesta_referencia_final': self.respuesta_referencia_final,
            'efectos_prohibidos': self.efectos_prohibidos,
            'criterios_especificos': self.criterios_especificos,
            'bloqueado': self.bloqueado, 'requiere_modelo': self.requiere_modelo,
            'revision_humana': self.revision_humana, 'origen': self.origen,
        }


@dataclass
class Hallazgo:
    codigo: str
    severidad: str            # 'critico' | 'mayor' | 'menor'
    detalle: str
    turno: Optional[int] = None

    def a_dict(self) -> Dict[str, Any]:
        return {'codigo': self.codigo, 'severidad': self.severidad,
                'detalle': self.detalle, 'turno': self.turno}


@dataclass
class TurnoObservado:
    indice: int
    usuario: str
    objetivo: str = ''
    accion_esperada: str = ''
    salidas: List[Dict[str, str]] = field(default_factory=list)
    estado_previo: Dict[str, Any] = field(default_factory=dict)
    estado_conversacion: Dict[str, Any] = field(default_factory=dict)
    catalogo: List[Dict[str, Any]] = field(default_factory=list)
    citas_creadas: List[Dict[str, Any]] = field(default_factory=list)
    citas_canceladas: List[Dict[str, Any]] = field(default_factory=list)
    pedidos_creados: List[Dict[str, Any]] = field(default_factory=list)
    pedidos_cancelados: List[Dict[str, Any]] = field(default_factory=list)
    alertas_activas: int = 0
    motivos_alerta: List[str] = field(default_factory=list)
    cotizacion: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def texto(self) -> str:
        return '\n'.join(s.get('texto') or '' for s in self.salidas)

    @property
    def salidas_ia(self) -> List[Dict[str, str]]:
        return [s for s in self.salidas if s.get('origen') == 'ia']

    def a_dict(self) -> Dict[str, Any]:
        return {'indice': self.indice, 'usuario': self.usuario,
                'objetivo': self.objetivo, 'accion_esperada': self.accion_esperada,
                'salidas': self.salidas, 'estado_previo': self.estado_previo,
                'estado_conversacion': self.estado_conversacion,
                'catalogo': self.catalogo,
                'citas_creadas': self.citas_creadas,
                'citas_canceladas': self.citas_canceladas,
                'pedidos_creados': self.pedidos_creados,
                'pedidos_cancelados': self.pedidos_cancelados,
                'alertas_activas': self.alertas_activas,
                'motivos_alerta': self.motivos_alerta,
                'cotizacion': self.cotizacion, 'error': self.error}


@dataclass
class ResultadoCaso:
    caso: Caso
    turnos: List[TurnoObservado] = field(default_factory=list)
    hallazgos: List[Hallazgo] = field(default_factory=list)
    estado: str = 'no_ejecutado'   # aprobado|fallido|bloqueado|omitido|no_ejecutado
    motivo: str = ''
    citas_finales: List[Dict[str, Any]] = field(default_factory=list)
    catalogo: List[Dict[str, Any]] = field(default_factory=list)
    duracion_ms: int = 0
    metadatos: Dict[str, Any] = field(default_factory=dict)

    @property
    def criticos(self) -> List[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad == 'critico']

    def a_dict(self) -> Dict[str, Any]:
        return {
            'caso': self.caso.id, 'categoria': self.caso.categoria,
            'criticidad_caso': self.caso.criticidad, 'split': self.caso.split,
            'estado': self.estado, 'motivo': self.motivo,
            'duracion_ms': self.duracion_ms, 'multiturno': self.caso.multiturno,
            'turnos': [t.a_dict() for t in self.turnos],
            'hallazgos': [h.a_dict() for h in self.hallazgos],
            'criticos': len(self.criticos),
            'citas_finales': self.citas_finales,
            'metadatos': self.metadatos,
        }
