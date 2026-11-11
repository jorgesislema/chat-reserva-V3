from pathlib import Path
import sys
repo = next(p for p in Path(__file__).resolve().parents if (p / 'crm' / 'store.py').is_file())
sys.path.insert(0, str(repo))
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from crm.store import initialize, connect
from crm import c02_services as svc
from crm import egress
from crm.chat_adapter import RespuestaChat

root = Path('.pytest_cache') / ('audit-repro-' + uuid4().hex)
root.mkdir()
path = str(root / 'isolated.db')
initialize(path)
with connect(path) as conn:
    for i in (1, 2):
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (?,?,?,'not-used','admin')",
                     (i, f'audit{i}@example.invalid', f'Audit {i}'))

# No HTTP or providers: deterministic nested delivery of a synthetic task.
created = svc.outbox_enqueue(path, channel='whatsapp', recipient='00000000111',
                            payload={'text': 'FICTITIOUS'}, origin='humano')
class Fake:
    count = 0
    def deliver(self, task):
        self.count += 1
        if self.count == 1:
            with connect(path) as conn:
                row = conn.execute('SELECT state,began_at FROM crm_outbox WHERE id=?',
                                   (task['id'],)).fetchone()
                print('human_transport_at_start', dict(row))
            future = datetime.now(timezone.utc) + timedelta(seconds=180)
            print('recovery_during_human_delivery', svc.outbox_recover_stale(path, timeout_seconds=120, clock=lambda: future))
            print('requeue_during_human_delivery', svc.outbox_requeue(path, outbox_id=task['id']))
            egress.egress_drain(path, self, worker='other-worker')
        return {'ok': True, 'provider_state': 'aceptado',
                'provider_message_id': 'fake-' + str(self.count)}
fake = Fake()
egress.egress_drain(path, fake, worker='first-worker')
print('human_delivery_count_for_one_task', fake.count)

# Published knowledge should be distinguished from an unpublished edit.
doc = svc.kb_upsert(path, doc_id=None, name='Audit document',
                    body_text='AUDIT_CANARY service costs 10', visibility='publico', actor=1)
doc_id = doc['doc_id']
print('publish', svc.kb_publish(path, doc_id=doc_id, actor=1).get('ok'))
print('public_hits_before_edit', len(svc.kb_retrieve_public(path, 'AUDIT_CANARY')))
svc.kb_upsert(path, doc_id=doc_id, name='Audit document',
              body_text='AUDIT_CANARY unapproved change costs 20',
              visibility='publico', state='borrador', actor=1)
print('public_hits_after_draft_edit', len(svc.kb_retrieve_public(path, 'AUDIT_CANARY')))

# Different users, same role and explicitly supplied conversation id.
svc.chat_memoria_guardar(path, 'audit-shared-id', turno=1, role='admin',
                         question='PRIVATE_AUDIT_QUESTION', question_busqueda='audit',
                         answer='PRIVATE_AUDIT_ANSWER', user_id=1)
class RecordingAdapter:
    modo = 'simulado'
    nombre = 'audit-local'
    def consultar(self, question, *, herramientas, rol, historial=None):
        print('other_user_receives_history_entries', len(historial or []))
        print('other_user_context_contains_canary',
              any(t.get('answer') == 'PRIVATE_AUDIT_ANSWER' for t in (historial or [])))
        return RespuestaChat(answer='synthetic answer')
svc.responder_chat_internal(path, 'audit question', role='admin',
                            conversation_id='audit-shared-id', user_id=2,
                            adaptador=RecordingAdapter())
print('isolated_database', str(root))
