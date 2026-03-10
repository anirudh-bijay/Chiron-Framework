class syscall:
    '''
    An abstraction for syscalls in the SSA form of the program.
    Depending on the architecture and the environment, the syscall
    will be implemented using suitable machine instructions and
    the appropriate syscall number.
    '''

    def __init__(self, name: str):
        '''
        Declare a syscall.

        :param str name: The name of the syscall.
        '''

        self._name = name

    @property
    def name(self) -> str:
        return self._name
    
    def __str__(self):
        return self.name

# Syscalls for turtle graphics.

penup    = syscall("penup")
pendown  = syscall("pendown")
forward  = syscall("forward")
backward = syscall("backward")
left     = syscall("left")
right    = syscall("right")
goto     = syscall("goto")