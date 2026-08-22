"""Knowledge base endpoints."""

from fastapi import APIRouter, Depends

from .. import repository
from ..auth import get_current_user
from ..schemas import KnowledgeCreate, KnowledgeOut, KnowledgeUpdate

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeOut])
def list_knowledge(
    category: str = "",
    user: dict = Depends(get_current_user),
):
    return repository.list_knowledge(category=category)


@router.post("", response_model=KnowledgeOut, status_code=201)
def add_knowledge(
    body: KnowledgeCreate,
    user: dict = Depends(get_current_user),
):
    return repository.add_knowledge(
        category=body.category,
        title=body.title,
        content=body.content,
        tags=body.tags,
    )


@router.patch("/{knowledge_id}", response_model=KnowledgeOut)
def update_knowledge(
    knowledge_id: str,
    body: KnowledgeUpdate,
    user: dict = Depends(get_current_user),
):
    doc = repository.update_knowledge(
        knowledge_id,
        **body.model_dump(exclude_unset=True),
    )
    if not doc:
        raise HTTPException(404, "知识库文档不存在")
    return doc


@router.delete("/{knowledge_id}", status_code=204)
def delete_knowledge(
    knowledge_id: str,
    user: dict = Depends(get_current_user),
):
    if not repository.delete_knowledge(knowledge_id):
        raise HTTPException(404, "知识库文档不存在")
    return None
