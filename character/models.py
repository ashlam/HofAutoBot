from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Character:
    id: str
    name: str
    order: int
    job_info: str
    level: str
    type: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Character':
        return cls(
            id=data['id'],
            name=data['name'],
            order=data['order'],
            job_info=data['job_info'],
            level=data['level'],
            type=data['type']
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'job_info': self.job_info,
            'order': self.order
        }

    def to_list(self) -> tuple:
        return (self.order, self.id, self.name, self.job_info) 