"""OpenAI-compatible LLM client for DeepSeek / tokenrhythm APIs."""

from langchain_openai import ChatOpenAI

from .config import LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 未配置")
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
    )


def chat_text(system: str, user: str, temperature: float = 0.2) -> str:
    llm = get_llm(temperature)
    response = llm.invoke([("system", system), ("human", user)])
    return str(response.content)
