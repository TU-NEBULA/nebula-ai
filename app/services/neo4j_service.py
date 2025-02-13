from fastapi import HTTPException
from app.core.database import get_db_session

def get_html_url_from_star(id: str) -> str:
    with get_db_session() as session:
        result = session.run('MATCH (s:Star {id: "' + id + '"}) RETURN s.html_file_url AS html', id=id)
        record = result.single()
        if record:
            return record["html"]
        else:
            raise HTTPException(status_code=404, detail="Node not found")
        