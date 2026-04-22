from dataclasses import dataclass, field
from typing import Optional

from ssa.label import label
from ssa.operands import operand
from ssa.statements import statement


@dataclass
class mips_label(label):
    '''
    A MIPS label. This is a label that can be used as a target for jumps and
    calls in MIPS assembly code.
    '''
    
    label: label

    def __str__(self):
        return f'{self.label}:'

@dataclass
class mips_instruction(statement):
    '''
    A MIPS assembly instruction.
    '''

    name: str
    operands: list[operand | label] = field(default_factory=list) # Variables are implicitly used as virtual registers.

    def __str__(self):
        if self.name in {'sw', 'lw'}:
            return ' ' * 8 + self.name.ljust(8) + f'{self.operands[0]}, {self.operands[2]}({self.operands[1]})'
        elif self.operands:
            return ' ' * 8 + self.name.ljust(8) + ', '.join(str(op) for op in self.operands)
        else:
            return ' ' * 8 + self.name
        
    @property
    def srcs(self) -> list[operand]:
        '''The source operands of this instruction.'''

        if self.name in {'j', 'jal'}:
            return []
        elif self.name in {'beq', 'bne', 'bgt', 'bge', 'blt', 'ble'}:
            return self.operands[0:2] # type: ignore
        elif self.name in {'beqz', 'bnez'}:
            return [self.operands[0]] # type: ignore
        return [op for op in self.operands[1:] if isinstance(op, operand)]
    
    @property
    def dest(self) -> Optional[operand]:
        '''The destination operand of this instruction, if any.'''
        
        if self.name == 'sw':
            return NotImplemented
        if self.name in {'j', 'jal', 'beq', 'bne', 'bgt', 'bge', 'blt', 'ble', 'beqz', 'bnez'}:
            return None
        return self.operands[0] if self.operands else None # type: ignore