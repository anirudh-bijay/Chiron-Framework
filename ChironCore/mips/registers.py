from dataclasses import dataclass
from typing import Any

from ssa.operands import operand


@dataclass
class physical_register(operand):
    '''
    Class for physical MIPS registers.
    '''

    name: str

    def __str__(self):
        return self.name
    
    def __eq__(self, other: Any):
        if not isinstance(other, physical_register):
            return NotImplemented
        return self.name == other.name
    
    def __hash__(self):
        return hash(self.name)