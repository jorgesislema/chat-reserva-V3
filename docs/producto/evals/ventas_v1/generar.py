"""Dataset ventas_v1: recorrido comercial en el simulador (datos sintéticos).

Genera fixture.json (negocio ficticio con zonas, promociones y regalo),
casos.jsonl/casos.csv y VALIDACION.md. No ejecuta el bot.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE = Path(__file__).resolve().parent.parent / 'tono_v2' / 'fixture.json'


def T(usuario, objetivo='', accion='', hechos=(), prohibido=()):
    turno = {'usuario': usuario}
    if objetivo:
        turno['objetivo'] = objetivo
    if accion:
        turno['accion_esperada'] = accion
    if hechos:
        turno['hechos_esperados'] = list(hechos)
    if prohibido:
        turno['prohibido'] = list(prohibido)
    return turno


def C(id, turnos, accion_final, criterios='', efectos=(), criticidad='alta',
      estado='base', split='desarrollo'):
    return {
        'id': id, 'old_id': None, 'version_dataset': '1.0',
        'categoria': 'ventas', 'criticidad': criticidad, 'split': split,
        'fixture': 'negocio_ventas_v1', 'negocio': 'dental',
        'estado_inicial': estado, 'reloj': '2030-01-07T09:00:00-05:00',
        'zona': 'America/Guayaquil', 'rol': 'cliente',
        'propiedad': 'conversacion_propia', 'turnos': turnos,
        'accion_esperada_final': accion_final,
        'respuesta_referencia_final': '',
        'efectos_prohibidos': list(efectos),
        'criterios_especificos': criterios,
        'bloqueado': None, 'requiere_modelo': False, 'revision_humana': True,
        'origen': 'ventas_v1',
    }


CASOS = [
    C('VEN01', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('2', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro', 'proponer_sin_crear', ('Total:',)),
        T('Sí, lo confirmo', 'confirmación', 'crear_un_pedido',
          ('quedó registrado', 'Pagas al recibir')),
    ], 'crear_un_pedido', criterios='Compra con retiro sin descuento; el pedido '
      'persiste antes de afirmarse.', efectos=('cita_creada',)),
    C('VEN02', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro con promo vigente', 'proponer_sin_crear',
          ('Descuento',)),
        T('Sí', 'confirmación', 'crear_un_pedido', ('USD 5,50',)),
    ], 'crear_un_pedido', criterios='Retiro con descuento vigente aplicado una vez.',
      efectos=('cita_creada',)),
    C('VEN03', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('A domicilio', 'domicilio', 'proponer_sin_crear'),
        T('Av. Ficticia 123', 'dirección', 'proponer_sin_crear'),
        T('Zona norte', 'zona con tarifa', 'proponer_sin_crear', ('USD 11,50',)),
        T('Sí', 'confirmación', 'crear_un_pedido', ('quedó registrado',)),
    ], 'crear_un_pedido', criterios='Domicilio con tarifa por zona.',
      efectos=('cita_creada',)),
    C('VEN04', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('A domicilio', 'domicilio', 'proponer_sin_crear'),
        T('Calle Ficticia 1', 'dirección', 'proponer_sin_crear'),
        T('Zona sur', 'zona sin tarifa', 'proponer_sin_crear',
          ('pendiente de confirmar',), ('Total:',)),
    ], 'sin_cambios', criterios='Sin tarifa no hay total definitivo ni pedido.',
      efectos=('cita_creada', 'pedido_creado')),
    C('VEN05', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('A domicilio', 'domicilio', 'proponer_sin_crear'),
        T('Av. Ficticia 123', 'dirección', 'proponer_sin_crear'),
        T('Zona norte', 'zona con tarifa', 'proponer_sin_crear', ('USD 11,50',),
          ('Descuento',)),
        T('Sí', 'confirmación', 'crear_un_pedido', ('quedó registrado',)),
    ], 'crear_un_pedido', criterios='La promo sólo-retiro no descuenta el domicilio.',
      efectos=('cita_creada',)),
    C('VEN06', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('A domicilio', 'domicilio', 'proponer_sin_crear'),
        T('Av. Ficticia 123', 'dirección', 'proponer_sin_crear'),
        T('Zona norte', 'zona con tarifa', 'proponer_sin_crear',
          ('De regalo', 'USD 11,50')),
        T('Sí', 'confirmación', 'crear_un_pedido', ('quedó registrado',)),
    ], 'crear_un_pedido', criterios='Regalo disponible incluido con existencias.',
      efectos=('cita_creada',)),
    C('VEN07', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro', 'proponer_sin_crear', ('Total:',)),
        T('Sí, pero no lo compres todavía', 'negación', 'sin_cambios',
          ('no he registrado',)),
    ], 'sin_cambios', criterios='La duda explícita no autoriza el pedido.',
      efectos=('cita_creada', 'pedido_creado')),
    C('VEN08', [
        T('Quiero comprar un cepillo', 'producto ambiguo', 'aclarar',
          ('¿Cuál quieres?',)),
        T('Ese', 'referencia al ofrecido', 'proponer_sin_crear'),
    ], 'proponer_sin_crear', criterios='Resuelve «ese» sin confundir variantes; '
      'proponer no crea el pedido.', efectos=('cita_creada', 'pedido_creado')),
    C('VEN09', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro', 'proponer_sin_crear', ('Total:',)),
        T('Sí', 'confirmación', 'crear_un_pedido', ('quedó registrado',)),
        T('Sí', 'repetición tras pausa', 'sin_respuesta_ia'),
    ], 'sin_respuesta_ia', criterios='La confirmación repetida no duplica el '
      'pedido ni reactiva la IA.', efectos=('cita_creada',)),
    C('VEN10', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Cancela el pedido', 'desiste antes de confirmar', 'sin_cambios',
          ('no he registrado',)),
    ], 'sin_cambios', criterios='Desistir antes de confirmar no escribe nada.',
      efectos=('cita_creada', 'pedido_creado')),
    C('VEN11', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro', 'proponer_sin_crear', ('Total:',)),
        T('Sí', 'confirmación', 'crear_un_pedido',
          ('quedó registrado', 'Pagas al recibir')),
    ], 'crear_un_pedido', criterios='Pago contra entrega queda pendiente; no se '
      'presenta como cobrado.', efectos=('cita_creada',)),
    C('VEN12', [
        T('Quiero comprar un cepillo suave', 'producto', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro', 'proponer_sin_crear', ('Total:',)),
        T('Sí', 'confirmación', 'crear_un_pedido', ('quedó registrado',)),
        T('¿Sigues ahí?', 'mensaje tras derivación', 'sin_respuesta_ia'),
    ], 'sin_respuesta_ia', criterios='Tras derivar al equipo no hay salida IA.',
      efectos=('cita_creada',)),
    C('VEN13', [
        T('Quiero comprar enjuague', 'producto sin stock', 'proponer_sin_crear'),
        T('1', 'cantidad', 'proponer_sin_crear'),
        T('Lo retiro en el local', 'retiro', 'sin_cambios', ('no tenemos',)),
    ], 'sin_cambios', criterios='Sin existencias no hay cotización ni pedido.',
      efectos=('cita_creada', 'pedido_creado')),
    C('VEN14', [
        T('Quiero comprar un cepillo', 'producto ambiguo', 'aclarar',
          ('¿Cuál quieres?',)),
        T('Mejor el otro', 'cambio de variante', 'proponer_sin_crear',
          ('Cepillo suave',)),
    ], 'proponer_sin_crear', criterios='«El otro» cambia a la segunda opción '
      'sin crear nada.', efectos=('cita_creada', 'pedido_creado')),
]


def main() -> int:
    base = json.loads(BASE.read_text(encoding='utf-8'))
    negocio = dict(base['negocio'])
    productos = [dict(p) for p in negocio.get('productos', [])]
    productos.append({'id': 'PR3', 'nombre': 'Cepillo mini', 'detalles': 'Regalo',
                      'price_cents': 0, 'moneda': 'USD', 'stock': 5, 'activo': True})
    negocio['productos'] = productos
    negocio['zonas_entrega'] = [
        {'codigo': 'NORTE', 'nombre': 'Zona norte', 'tarifa': 500, 'activa': True},
        {'codigo': 'SUR', 'nombre': 'Zona sur', 'tarifa': None, 'activa': True},
    ]
    negocio['promociones'] = [
        {'codigo': 'RETIRO100', 'nombre': 'Descuento por retiro', 'tipo': 'monto',
         'valor': 100, 'moneda': 'USD', 'combinable': False, 'modo': 'retiro',
         'desde': '2020-01-01', 'hasta': '2035-01-01', 'activa': True,
         'items': ['PR1']},
        {'codigo': 'CONREGALO', 'nombre': 'Promo con regalo', 'tipo': 'monto',
         'valor': 0, 'moneda': 'USD', 'combinable': False, 'modo': 'ambos',
         'desde': '2020-01-01', 'hasta': '2035-01-01', 'activa': True,
         'items': ['PR1'], 'regalos': [{'item': 'PR3', 'cantidad': 1}]},
    ]
    fixture = dict(base)
    fixture['id'] = 'negocio_ventas_v1'
    fixture['negocio'] = negocio
    (AQUI / 'fixture.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2),
                                       encoding='utf-8')
    with (AQUI / 'casos.jsonl').open('w', encoding='utf-8', newline='\n') as f:
        for datos in CASOS:
            f.write(json.dumps(datos, ensure_ascii=False) + '\n')
    with (AQUI / 'casos.csv').open('w', encoding='utf-8', newline='') as f:
        campos = ['id', 'categoria', 'criticidad', 'split', 'estado_inicial',
                  'turnos', 'accion_esperada_final', 'efectos_prohibidos',
                  'criterios_especificos']
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for datos in CASOS:
            fila = {k: datos.get(k) for k in campos}
            for k in ('turnos', 'efectos_prohibidos'):
                fila[k] = json.dumps(fila[k], ensure_ascii=False)
            w.writerow(fila)
    # Validación estructural ligera (el umbral de 200 casos es de tono_v2).
    errores = []
    ids = [c['id'] for c in CASOS]
    if len(set(ids)) != len(ids):
        errores.append('IDs duplicados')
    for c in CASOS:
        if not c['turnos']:
            errores.append('%s sin turnos' % c['id'])
        if c['accion_esperada_final'] not in (
                'consultar', 'aclarar', 'sin_cambios', 'proponer_sin_crear',
                'proponer_sin_cambiar', 'crear_una_cita', 'crear_un_pedido',
                'cancelar_A1', 'cancelar_pedido', 'derivar', 'derivar_prioritario',
                'ofrecer_humano', 'sin_respuesta_ia', 'enviar_archivo_autorizado',
                'reconciliar', 'verificar_estado'):
            errores.append('%s acción final inválida' % c['id'])
    if errores:
        print('Dataset inválido: %s' % errores)
        return 1
    resumen = {'total': len(CASOS),
               'multiturno': sum(1 for c in CASOS if len(c['turnos']) > 1),
               'turnos_usuario': sum(len(c['turnos']) for c in CASOS)}
    (AQUI / 'VALIDACION.md').write_text(
        '# Validación del dataset ventas_v1\n\nGenerado por `generar.py`. '
        'Datos sintéticos. No ejecuta el bot.\n\n| Métrica | Valor |\n|---|---:|\n'
        '| Casos totales | %d |\n| Conversaciones multiturno | %d |\n'
        '| Mensajes de usuario | %d |\n' % (
            resumen['total'], resumen['multiturno'], resumen['turnos_usuario']),
        encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
