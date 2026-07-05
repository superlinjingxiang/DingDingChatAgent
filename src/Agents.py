from langchain.agents import AgentExecutor,create_tool_calling_agent,create_structured_chat_agent
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from langchain_core.runnables import RunnableLambda
from .Prompt import PromptClass
from .Memory import MemoryClass
from .Emotion import EmotionClass
from langchain_core.caches import InMemoryCache
from .Storage import get_user

from .Tools import search,get_info_from_local,create_todo,checkSchedule,SetSchedule,SearchSchedule,ModifySchedule,DelSchedule,ConfirmDelSchedule
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()
import os
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_API_BASE")
os.environ["DEEPSEEK_API_KEY"] = os.getenv("DEEPSEEK_API_KEY")
os.environ["DEEPSEEK_API_BASE"] = os.getenv("DEEPSEEK_API_BASE")
#添加缓存
from langchain_core.globals import set_llm_cache
set_llm_cache(InMemoryCache())


class AgentClass:
    def __init__(self):
        # 基础组件初始化
        fallback_llm = ChatDeepSeek(model=os.getenv("BACKUP_MODEL"))
        self.modelname = os.getenv("BASE_MODEL")
        self.chatmodel = ChatOpenAI(model=self.modelname).with_fallbacks([fallback_llm])
        self.tools = [search,get_info_from_local,create_todo,checkSchedule,SetSchedule,SearchSchedule,ModifySchedule,DelSchedule,ConfirmDelSchedule]
        self.memorykey = os.getenv("MEMORY_KEY")
        self.memory = MemoryClass(memorykey=self.memorykey,model=self.modelname)
        self.emotion = EmotionClass(model=self.modelname)
        
        # 初始化情绪状态
        self.feeling = {"feeling":"default","score":5}
        
        # 创建动态 agent 执行器
        self.agent_executor = self._create_dynamic_agent()

    def _create_dynamic_agent(self):
        """使用 RunnableLambda 创建动态 agent 执行器"""
        
        def build_agent_chain(inputs):
            """动态构建 agent chain 的函数"""
            # 使用当前最新的情绪状态创建 prompt
            current_prompt = PromptClass(
                memorykey=self.memorykey, 
                feeling=self.feeling
            ).Prompt_Structure()
            
            print("Dynamic prompt created with feeling:", self.feeling)
            print("Current prompt:", current_prompt)
            
            # 创建 agent
            agent = create_tool_calling_agent(
                self.chatmodel,
                self.tools,
                current_prompt
            )
            
            # 创建 executor
            executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=self.memory.set_memory(session_id=get_user("userid")),
                verbose=True
            )
            
            # 执行并返回结果
            return executor.invoke(inputs)
        
        # 返回 RunnableLambda，它会在每次调用时动态构建链
        return RunnableLambda(build_agent_chain)

    def run_agent(self, input):
        """运行 agent"""
        # 1. 情绪检测 - 更新情绪状态
        detected_feeling = self.emotion.Emotion_Sensing(input)
        if detected_feeling:
            self.feeling = detected_feeling
            print("Emotion updated:", self.feeling)
        
        # 2. 动态执行 - RunnableLambda 会自动使用最新的情绪状态构建 agent
        response = self.agent_executor.invoke({"input": input})
        
        return response
