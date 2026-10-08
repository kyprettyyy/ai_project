import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/evaluation'))
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.services.batch_test_service import BatchTestService
from app.core.errors import BusinessException

class ResumeTest(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine('sqlite+aiosqlite://')
  async with self.engine.begin() as c:
   await c.run_sync(TestTask.metadata.create_all)
   await c.run_sync(TestResult.metadata.create_all)
  self.session=async_sessionmaker(self.engine,expire_on_commit=False)()
  self.task=TestTask(id='task',user_id=1,scene_id='scene',models=json.dumps(['a','b']),
   config=json.dumps({'promptSnapshot':[{'id':'p1','title':'one','content':'first'}, {'id':'p2','title':'two','content':'second'}]}),
   status='failed',total_subtasks=4,completed_subtasks=3,is_delete=0)
  self.session.add(self.task)
  self.session.add(TestResult(id='r1',task_id='task',user_id=1,scene_id='scene',prompt_id='p1',model_name='a',input_prompt='first',output_text='ok',is_delete=0))
  self.session.add(TestResult(id='r2',task_id='task',user_id=1,scene_id='scene',prompt_id='p2',model_name='a',input_prompt='second',output_text='',is_delete=0))
  await self.session.commit()
 async def asyncTearDown(self):
  await self.session.close();await self.engine.dispose()
 async def test_resume_only_missing_pairs_and_reconcile_counter(self):
  with patch('app.services.batch_test_runner.start_batch') as start:
   result=await BatchTestService.resume_batch_test(self.session,'task',1)
  self.assertEqual(result,{'taskId':'task','retainedResults':2,'retrySubtasks':2})
  self.assertEqual(self.task.completed_subtasks,2)
  self.assertEqual({(x['modelName'],x['promptId']) for x in start.call_args.args[1]},{('b','p1'),('b','p2')})
  self.assertEqual(self.task.status,'pending')
 async def test_other_user_cannot_resume(self):
  with self.assertRaises(BusinessException):await BatchTestService.resume_batch_test(self.session,'task',2)
 async def test_double_click_does_not_schedule_twice(self):
  with patch('app.services.batch_test_runner.start_batch') as start:
   await BatchTestService.resume_batch_test(self.session,'task',1)
   with self.assertRaises(BusinessException):await BatchTestService.resume_batch_test(self.session,'task',1)
   self.assertEqual(start.call_count,1)
 async def test_active_coordinator_cannot_resume(self):
  with patch('app.services.batch_test_runner.is_batch_running',return_value=True):
   with self.assertRaises(BusinessException):await BatchTestService.resume_batch_test(self.session,'task',1)
 async def test_all_results_saved_can_finalize_without_paid_calls(self):
  for p in ['p1','p2']:
   self.session.add(TestResult(id='b'+p,task_id='task',user_id=1,scene_id='scene',prompt_id=p,model_name='b',input_prompt=p,output_text='ok',is_delete=0))
  await self.session.commit()
  with patch('app.services.batch_test_runner.start_batch') as start:
   r=await BatchTestService.resume_batch_test(self.session,'task',1)
   start.assert_not_called()
  self.assertEqual(r['retrySubtasks'],0);self.assertEqual(self.task.status,'completed')
 async def test_restart_runs_all_pairs_and_preserves_original_results(self):
  from types import SimpleNamespace
  from unittest.mock import AsyncMock
  with patch('app.services.model_service.ModelService.get_all_models', new=AsyncMock(return_value=[SimpleNamespace(id='a'),SimpleNamespace(id='b')])), patch('app.services.batch_test_runner.start_batch') as start:
   new_id=await BatchTestService.restart_batch_test(self.session,'task',1)
  new_task=await self.session.get(TestTask,new_id)
  self.assertNotEqual(new_id,'task')
  self.assertEqual(new_task.completed_subtasks,0)
  self.assertEqual(len(start.call_args.args[1]),4)
  self.assertEqual(json.loads(new_task.config)['promptSnapshot'],json.loads(self.task.config)['promptSnapshot'])
  self.assertEqual(self.task.status,'failed')
  self.assertIsNotNone(await self.session.get(TestResult,'r1'))
 async def test_restart_rejects_missing_model_without_scheduling(self):
  from unittest.mock import AsyncMock
  with patch('app.services.model_service.ModelService.get_all_models',new=AsyncMock(return_value=[])), patch('app.services.batch_test_runner.start_batch') as start:
   with self.assertRaises(BusinessException):await BatchTestService.restart_batch_test(self.session,'task',1)
   start.assert_not_called()
 async def test_other_user_cannot_restart(self):
  with self.assertRaises(BusinessException):await BatchTestService.restart_batch_test(self.session,'task',2)
