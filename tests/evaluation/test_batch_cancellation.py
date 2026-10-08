import sys,unittest,asyncio
from pathlib import Path
from unittest.mock import MagicMock,AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/evaluation'))
from app.services.batch_cancellation import register_client,cancel_batch_calls,unregister_client
from app.services.batch_test_runner import start_batch,cancel_batch
class CancellationTest(unittest.IsolatedAsyncioTestCase):
 def test_deleted_batch_cannot_start_another_answer_or_judge(self):
  c=MagicMock(); original=c.chat.completions.create
  register_client('deleted-unit',c)
  c.chat.completions.create(model='m')
  original.assert_called_once()
  cancel_batch_calls('deleted-unit')
  c.close.assert_called_once()
  with self.assertRaisesRegex(RuntimeError,'任务已删除'):
   c.chat.completions.create(model='judge')
  original.assert_called_once()
  late=MagicMock()
  with self.assertRaises(RuntimeError): register_client('deleted-unit',late)
  late.close.assert_called_once()
  unregister_client('deleted-unit',c)
 async def test_cancel_before_coordinator_starts_skips_all_workers(self):
  worker=MagicMock()
  start_batch('cancel-coordinator-unit',[{'taskId':'cancel-coordinator-unit'}]*10,worker)
  cancel_batch('cancel-coordinator-unit')
  await asyncio.sleep(.01)
  worker.assert_not_called()
