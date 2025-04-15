from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class CookieConfig:
    NO: str = ""
    id: str = ""
    PHPSESSID: str = ""
    d6aeb6c8e019feacab64894fb458c271: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'CookieConfig':
        return cls(
            NO=data.get('NO', ''),
            id=data.get('id', ''),
            PHPSESSID=data.get('PHPSESSID', ''),
            d6aeb6c8e019feacab64894fb458c271=data.get('d6aeb6c8e019feacab64894fb458c271', '')
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            'NO': self.NO,
            'id': self.id,
            'PHPSESSID': self.PHPSESSID,
            'd6aeb6c8e019feacab64894fb458c271': self.d6aeb6c8e019feacab64894fb458c271
        }

    def to_cookie_string(self) -> str:
        return '; '.join([f"{k}={v}" for k, v in self.to_dict().items() if v]) 