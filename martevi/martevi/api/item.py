
from typing import List

from fastapi import APIRouter
from martevi.schema import Item

router = APIRouter(tags=["Item"])

@router.get(
    '/items',
    response_model=List[Item]
)
async def read_items() -> List[Item]:
    """
    List all Items
    """
    ...


@router.post(
    '/items', response_model=Item
)
def create_item(item: Item) -> Item:
    """
    Create a Item
    """
    ...


@router.get(
    '/items/{item_id}',
    response_model=Item,
)
def read_item(item_id: str)-> Item:
    """
    Reterive a Item
    """
    ...


@router.put(
    '/items/{item_id}',
    response_model=Item,
)
def update_item(item_id: str)-> Item:
    """
    Update a Item
    """
    ...