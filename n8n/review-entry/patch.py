"""Scope review entry changes to existing policies and authenticated review storage."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
cards=load('review_entry_cards','n8n/my-requests-simplification/patch.py')
reviews=load('review_entry_backend','n8n/media-reviews/patch.py')
CARD_IDS={'0e67KTcphqxEKNsh','HXtTzVTrpNZMZVt3','snakeMyRequestsV1','snakeStatusV1','snakeStatusInspectV1'}
def build(source,env):
    patched=cards.build(source)
    scoped=[new if old['id'] in CARD_IDS else old for old,new in zip(source,patched)]
    return reviews.build(scoped,env)
