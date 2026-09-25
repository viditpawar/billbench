from pydantic import BaseModel


class Bill(BaseModel):
    bill_id: str              # e.g. "119-hr-1234"
    congress: int
    bill_type: str
    number: int
    title: str
    text_version: str         # e.g. "Introduced in House"
    text_date: str
    text: str
    crs_summary: str
    crs_version: str          # actionDesc of the CRS summary
    crs_action_date: str
    match_method: str         # "exact" | "date_fallback"
    n_tokens: int
    stratum: str = ""
