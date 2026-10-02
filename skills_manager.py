import os
import glob
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client

logger = logging.getLogger(SkillsManager)

class SkillsManager:
    "
    Loads and manages skills in Antigravity format:
    1. Local files in skills/<skill_name>/SKILL.md
    2. Dynamic skills stored in Supabase table gent_skills
    "
    def __init__(self, skills_dir: str = skills):
        self.skills_dir = skills_dir
        self.supabase: Optional[Client] = None
        self._init_supabase()

    def _init_supabase(self):
        sb_url = os.getenv(SUPABASE_URL)
        sb_key = os.getenv(SUPABASE_KEY) or os.getenv(SUPABASE_SERVICE_ROLE_KEY)
        if sb_url and sb_key:
            try:
                self.supabase = create_client(sb_url, sb_key)
            except Exception as e:
                logger.error(fFailed to connect to Supabase for skills: {e})

    def list_all_skills(self) -> List[Dict[str, Any]]:
        skills = []
        # 1. Local skills
        if os.path.exists(self.skills_dir):
            for skill_path in glob.glob(os.path.join(self.skills_dir, *, SKILL.md)):
                skill_name = os.path.basename(os.path.dirname(skill_path))
                try:
                    with open(skill_path, r, encoding=utf-8) as f:
                        content = f.read()
                    skills.append({
                        id: flocal-{skill_name},
                        name: skill_name,
                        source: local,
                        is_active: True,
                        content: content
                    })
                except Exception as e:
                    logger.warning(fError reading skill {skill_path}: {e})

        # 2. Supabase dynamic skills
        if self.supabase:
            try:
                res = self.supabase.table(agent_skills).select(*).execute()
                for item in res.data or []:
                    skills.append({
                        id: str(item.get(id)),
                        name: item.get(name),
                        source: supabase,
                        is_active: item.get(is_active, True),
                        content: item.get(content, ")
 })
 except Exception as e:
 logger.warning(fError fetching skills from Supabase: {e})

 return skills

 def get_system_prompt_additions(self) -> str:
 "Assembles prompt injection from all active skills."
 active = [s for s in self.list_all_skills() if s.get(is_active)]
 if not active:
 return 

 sections = [\n\n## ACTIVE ANTIGRAVITY SKILLS & PLUGINS:]
 for s in active:
 sections.append(f\n### Skill: {s['name']}\n{s['content']}\n)
 return \n.join(sections)

skills_manager = SkillsManager()
