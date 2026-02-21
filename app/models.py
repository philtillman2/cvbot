from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Candidate models (matching JSON schema) ---

class DateRange(BaseModel):
    year: int
    month: int


class EndDate(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    present: Optional[bool] = None


class Employer(BaseModel):
    name: str
    description: str = ""
    link: str = ""
    sector: str = ""
    location: str = ""


class WorkItem(BaseModel):
    title: str
    description: str = ""
    contribution: str = ""


class Role(BaseModel):
    start: DateRange
    end: EndDate
    title: str = ""
    employment_type: str = ""
    items: list[WorkItem] = []


class WorkEntry(BaseModel):
    start: DateRange
    end: EndDate
    employer: Employer
    roles: list[Role] = []


class Dissertation(BaseModel):
    title: str = ""
    description: str = ""
    advisors: list[str] = []
    primary_research: str = ""


class Education(BaseModel):
    start: DateRange
    end: EndDate
    degree: str
    institution: str
    subjects: list[str] = []
    GPA: str = ""
    notes: str = ""
    completed: bool = True
    dissertation: Optional[Dissertation] = None


class Author(BaseModel):
    first_name: str = ""
    last_name: str = ""


class PageRange(BaseModel):
    start: Optional[int] = None
    end: Optional[int] = None


class Publication(BaseModel):
    title: str = ""
    abstract: str = ""
    authors: list[Author] = []
    date: Optional[dict] = None
    journal: str = ""
    publication: str = ""
    volume: Optional[int] = None
    issue: Optional[int] = None
    pages: Optional[PageRange] = None
    publisher: str = ""
    editor: str = ""
    isbn: Optional[int] = None
    doi: str = ""
    links: list[str] = []


class CandidateProfile(BaseModel):
    summary: str = ""
    skills: str = ""
    work: list[WorkEntry] = []
    education: list[Education] = []
    publications: list[Publication] = []


# --- API / DB models ---

class ConversationCreate(BaseModel):
    candidate_id: str


class ConversationRename(BaseModel):
    title: str


class ConversationOut(BaseModel):
    id: int
    candidate_id: str
    title: Optional[str]
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ChatRequest(BaseModel):
    message: str
    model: str = "openai/gpt-4o-mini"


class CandidateOut(BaseModel):
    id: str
    display_name: str


class JobFitRequest(BaseModel):
    candidate_id: str
    job_description: str
    model: str = "openai/gpt-4o-mini"
