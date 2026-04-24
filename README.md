# Program Analysis with Chiron

A framework to teach program analysis, verification, and testing in a graduate-level course.

```
░█████╗░██╗░░██╗██╗██████╗░░█████╗░███╗░░██╗
██╔══██╗██║░░██║██║██╔══██╗██╔══██╗████╗░██║
██║░░╚═╝███████║██║██████╔╝██║░░██║██╔██╗██║
██║░░██╗██╔══██║██║██╔══██╗██║░░██║██║╚████║
╚█████╔╝██║░░██║██║██║░░██║╚█████╔╝██║░╚███║
░╚════╝░╚═╝░░╚═╝╚═╝╚═╝░░╚═╝░╚════╝░╚═╝░░╚══╝
```
[![Architecture Diagram](./assets/Architecture_Digram.png)](./assets/Architecture_Digram.png)

## Video Demo 

Fuzzer Demo in Chiron Framework. Click the image below

<a href="https://raw.githubusercontent.com/PRAISE-group/Chiron-Framework/master/assets/Fuzzer_Demo.mp4" title="Link Title"><img src="https://raw.githubusercontent.com/PRAISE-group/Chiron-Framework/master/assets/Screenshot%20from%202025-01-16%2012-34-51.png" alt="Alternate Text" /></a>

- [Some nice words in WSS' 2023, IIT Delhi about Chiron Framework](https://www.linkedin.com/posts/ashupdsce_wss-wss2023-iitd-activity-7150851909581463553-bJ6-?utm_source=share&utm_medium=member_desktop)
- [ASE 2023 Conference Page](https://conf.researchr.org/details/ase-2023/ase-2023-papers/117/An-Integrated-Program-Analysis-Framework-for-Graduate-Courses-in-Programming-Language)
- [Read our research paper here](https://ieeexplore.ieee.org/document/10298417)

## Citation 

If you want to cite this work, you may use this.

```
@INPROCEEDINGS{ase_2023_chiron,
  author={Chatterjee, Prantik and Kalita, Pankaj Kumar and Lahiri, Sumit and Muduli, Sujit Kumar and Singh, Vishal and Takhar, Gourav and Roy, Subhajit},
  booktitle={2023 38th IEEE/ACM International Conference on Automated Software Engineering (ASE)}, 
  title={An Integrated Program Analysis Framework for Graduate Courses in Programming Languages and Software Engineering}, 
  year={2023},
  volume={},
  number={},
  pages={598-610},
  keywords={Surveys;Computer languages;Program processors;Software algorithms;Software systems;Task analysis;Engines;program analysis verification and testing;programming languages;software engineering;graduate level course;education},
  doi={10.1109/ASE56229.2023.00101}}
```
### Installing Dependencies

You need to install `java` Runtime and dependency libs. You may also need to install java JDK (`javac`) on older Windows machine.
Python, pip and other packages are also required. Please follow the steps given below.

If you are using Windows, we highly recommend using `powershell` instead of `wsl` or `windows command prompt`.

- [https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.5](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.5)

```pwsh
winget search --id Microsoft.PowerShell

Name               Id                           Version Source
---------------------------------------------------------------
PowerShell         Microsoft.PowerShell         7.5.4.0 winget
PowerShell Preview Microsoft.PowerShell.Preview 7.6.0.6 winget

winget install --id Microsoft.PowerShell --source winget
```
 
#### Installing Java

Installing the lastest java package for your operating system. 

- [https://www.java.com/en/download/manual.jsp](https://www.java.com/en/download/manual.jsp)

```bash
$ java --version 
openjdk 21.0.9 2025-10-21 LTS
OpenJDK Runtime Environment Temurin-21.0.9+10 (build 21.0.9+10-LTS)
OpenJDK 64-Bit Server VM Temurin-21.0.9+10 (build 21.0.9+10-LTS, mixed mode, sharing)

$ javac --version
javac 21.0.9
```

#### Installing Python.

We recommend using the latest version of Python (`python3.14`) with python install manager.

- [https://www.python.org/](https://www.python.org/)

```bash
$ python --version 
Python 3.11.3

$ python3.14 --version
Python 3.14.2
```

#### Installing UV (astral) package manager.

We recommend using `uv` package manager to handle python dependencies for Chiron. 
Virtual environment with `uv` also works without issues.

If you intend to use `pip` and system-wide install `python`, install the following packages using pip instead of uv.

- [https://docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_1)
- [https://www.antlr.org/download.html](https://www.antlr.org/download.html)

These packages are required, you may need to try different versions of these packages, for python3.10 or python3.11. 

- [https://pypi.org/project/antlr4-python3-runtime/](https://pypi.org/project/antlr4-python3-runtime/)
- [https://pypi.org/project/numpy/](https://pypi.org/project/numpy/)
- [https://pypi.org/project/z3-solver/](https://pypi.org/project/z3-solver/)
- [https://pypi.org/project/networkx/](https://pypi.org/project/networkx/)

```bash
$ uv add antlr4-python3-runtime==4.13.2 networkx z3-solver numpy
Resolved 5 packages in 127ms
Audited 4 packages in 30ms

# If you do not want to use uv package manager.
$ pip install antlr4-python3-runtime==4.13.2 networkx z3-solver numpy 

# On UNIX/MacOSX platform, run this. On Windows (10/11) not required.
$ sudo apt-get install python3-tk
```

### Generating the ANTLR files.

The `antlr` files need to be rebuilt if any changes are made to the `tlang.g4` file or when installing Chiron for the first time.
We use a visitor pattern to generate the AST from parsing. 

- [https://www.antlr.org/about.html](https://www.antlr.org/about.html)

You may download the latest antlr version complete jar binary to the `\ChironCore\extlib` folder and use it.

- [https://www.antlr.org/download/antlr-4.13.2-complete.jar](https://www.antlr.org/download/antlr-4.13.2-complete.jar)

From the directory shown in the command below, build the antlr related visitor code with java and latest antlr runtime jar files.

```
$ cd ChironCore/turtparse
$ java -cp ../extlib/antlr-4.13.2-complete.jar org.antlr.v4.Tool -Dlanguage=Python3 -visitor -no-listener tlang.g4
```

### Running an example

The main directory for source files is `ChironCore`. We have examples of the turtle programs in `examples` folder.
To pass parameters (input params) for running a turtle program, use the `-d` flag. Pass the parameters as a python dictionary. 

```bash
$ cd ChironCore
$ ./chiron.py -r ./example/example1.tl -d '{":x": 20, ":y": 30, ":z": 20, ":p": 40}'
```

If you are using `uv` package manager, which we highly recommend using, run `Chiron` using the following commands.
Always prefix with `uv run` instead of running with `python`.

```bash
$ cd ChironCore
$ uv run chiron.py -r ./example/example1.tl -d '{":x": 20, ":y": 30, ":z": 20, ":p": 40}'
```

### See help for other command line options

Running with system-wide installed python.

```bash
# You may need to use python instead of python3.
$ python3 chiron.py --help


░█████╗░██╗░░██╗██╗██████╗░░█████╗░███╗░░██╗
██╔══██╗██║░░██║██║██╔══██╗██╔══██╗████╗░██║
██║░░╚═╝███████║██║██████╔╝██║░░██║██╔██╗██║
██║░░██╗██╔══██║██║██╔══██╗██║░░██║██║╚████║
╚█████╔╝██║░░██║██║██║░░██║╚█████╔╝██║░╚███║
░╚════╝░╚═╝░░╚═╝╚═╝╚═╝░░╚═╝░╚════╝░╚═╝░░╚══╝


Chiron v1.0.1
------------
usage: chiron.py [-h] [-p] [-r] [-mips] [-3ac] [-ssa] [-no_ssa_dce] [-gr] [-b] [-k] [-z] [-t TIMEOUT] [-d PARAMS]
                 [-c CONSTPARAMS] [-se] [-ai] [-dfa] [-sbfl] [-bg BUGGY] [-vars INPUTVARSLIST] [-nt NTESTS]
                 [-pop POPSIZE] [-cp CXPB] [-mp MUTPB] [-cfg_gen] [-cfg_dump] [-dump] [-ng NGEN] [-vb VERBOSE]
                 progfl

Program Analysis Framework for ChironLang Programs.

positional arguments:
  progfl

options:
  -h, --help            show this help message and exit
  -p, --ir              pretty printing the IR of a Chiron program to stdout (terminal)
  -r, --run             execute Chiron program, the figure/shapes the turle draws is shown in a UI.
  -mips, --mips_asm     compile Chiron program to MIPS assembly.
  -3ac, --three_address_code
                        convert Chiron IR to three address code and print the result to stdout.
  -ssa, --ssa           convert Chiron IR to SSA form and print the result to stdout.
  -no_ssa_dce, --no_ssa_dce
                        do not perform dead code elimination in SSA form; print the semi-pruned SSA form
  -gr, --fuzzer_gen_rand
                        Generate random input seeds for the fuzzer before fuzzing starts.
  -b, --bin             load binary IR of a Chiron program
  -z, --fuzz            Run fuzzer on a Chiron program (seed values with '-d' or '--params' flag needed.)
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout Parameter for Analysis (in secs). This is the total timeout.
  -d PARAMS, --params PARAMS
                        pass variable values to Chiron program in python dictionary format
  -c CONSTPARAMS, --constparams CONSTPARAMS
                        pass variable(for which you have to find values using circuit equivalence) values to Chiron program
                        in python dictionary format
  -se, --symbolicExecution
                        Run Symbolic Execution on a Chiron program (seed values with '-d' or '--params' flag needed) to
                        generate test cases along all possible paths.
  -ai, --abstractInterpretation
                        Run abstract interpretation on a Chiron Program.
  -dfa, --dataFlowAnalysis
                        Run data flow analysis using worklist algorithm on a Chiron Program.
  -sbfl, --SBFL         Run Spectrum-basedFault localizer on Chiron program
  -bg BUGGY, --buggy BUGGY
                        buggy Chiron program path
  -vars INPUTVARSLIST, --inputVarsList INPUTVARSLIST
                        A list of input variables of given Chiron program
  -nt NTESTS, --ntests NTESTS
                        number of tests to generate
  -pop POPSIZE, --popsize POPSIZE
                        population size for Genetic Algorithm.
  -cp CXPB, --cxpb CXPB
                        cross-over probability
  -mp MUTPB, --mutpb MUTPB
                        mutation probability
  -ng NGEN, --ngen NGEN
                        number of times Genetic Algorithm iterates
  -vb VERBOSE, --verbose VERBOSE
                        To display computation to Console

```

Running with `uv`.

```bash
uv run chiron.py --help
Chiron v5.3

    ░█████╗░██╗░░██╗██╗██████╗░░█████╗░███╗░░██╗
    ██╔══██╗██║░░██║██║██╔══██╗██╔══██╗████╗░██║
    ██║░░╚═╝███████║██║██████╔╝██║░░██║██╔██╗██║
    ██║░░██╗██╔══██║██║██╔══██╗██║░░██║██║╚████║
    ╚█████╔╝██║░░██║██║██║░░██║╚█████╔╝██║░╚███║
    ░╚════╝░╚═╝░░╚═╝╚═╝╚═╝░░╚═╝░╚════╝░╚═╝░░╚══╝
    
usage: chiron.py [-h] [-p] [-r] [-mips] [-3ac] [-ssa] [-no_ssa_dce] [-gr] [-b] [-k] [-z] [-t TIMEOUT] [-d PARAMS]
                 [-c CONSTPARAMS] [-se] [-ai] [-dfa] [-sbfl] [-bg BUGGY] [-vars INPUTVARSLIST] [-nt NTESTS]
                 [-pop POPSIZE] [-cp CXPB] [-mp MUTPB] [-cfg_gen] [-cfg_dump] [-dump] [-ng NGEN] [-vb VERBOSE]
                 progfl

Program Analysis Framework for ChironLang Programs.

positional arguments:
  progfl

options:
  -h, --help            show this help message and exit
  -p, --ir              pretty printing the IR of a Chiron program to stdout (terminal)
  -r, --run             execute Chiron program, the figure/shapes the turle draws is shown in a UI.
  -mips, --mips_asm     compile Chiron program to MIPS assembly.
  -3ac, --three_address_code
                        convert Chiron IR to three address code and print the result to stdout.
  -ssa, --ssa           convert Chiron IR to SSA form and print the result to stdout.
  -no_ssa_dce, --no_ssa_dce
                        do not perform dead code elimination in SSA form; print the semi-pruned SSA form
  -gr, --fuzzer_gen_rand
                        Generate random input seeds for the fuzzer before fuzzing starts.
  -b, --bin             load binary IR of a Chiron program
  -k, --hooks           Run hooks for Kachua.
  -z, --fuzz            Run fuzzer on a Chiron program (seed values with '-d' or '--params' flag needed.)
  -t, --timeout TIMEOUT
                        Timeout Parameter for Analysis (in secs). This is the total timeout.
  -d, --params PARAMS   pass variable values to Chiron program in python dictionary format
  -c, --constparams CONSTPARAMS
                        pass variable(for which you have to find values using circuit equivalence) values to Chiron program in python dictionary format
  -se, --symbolicExecution
                        Run Symbolic Execution on a Chiron program (seed values with '-d' or '--params' flag needed) to generate test cases along all possible paths.
  -ai, --abstractInterpretation
                        Run abstract interpretation on a Chiron Program.
  -dfa, --dataFlowAnalysis
                        Run data flow analysis using worklist algorithm on a Chiron Program.
  -sbfl, --SBFL         Run Spectrum-basedFault localizer on Chiron program
  -bg, --buggy BUGGY    buggy Chiron program path
  -vars, --inputVarsList INPUTVARSLIST
                        A list of input variables of given Chiron program
  -nt, --ntests NTESTS  number of tests to generate
  -pop, --popsize POPSIZE
                        population size for Genetic Algorithm.
  -cp, --cxpb CXPB      cross-over probability
  -mp, --mutpb MUTPB    mutation probability
  -cfg_gen, --control_flow
                        Generate the CFG of the given turtle program
  -cfg_dump, --dump_cfg
                        Generate the CFG of the given turtle program
  -dump, --dump_ir      Dump the IR to a .kw (pickle file)
  -ng, --ngen NGEN      number of times Genetic Algorithm iterates
  -vb, --verbose VERBOSE
                        To display computation to Console
```

