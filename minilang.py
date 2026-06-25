"""
================================================================================
  MiniLang Compiler & Virtual Machine
================================================================================
  A complete, from-scratch implementation of:
    1. Lexer       — tokenizes raw source code
    2. Parser      — builds an Abstract Syntax Tree (AST)
    3. Compiler    — walks the AST and emits stack-based bytecode
    4. VM          — executes the bytecode

  Language: MiniLang  (integer arithmetic, variables, print)
  Author  : Compiler Engineering Demo
================================================================================
"""

import sys


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 – LANGUAGE SPECIFICATION
# ══════════════════════════════════════════════════════════════════════════════
#
#  MiniLang grammar (EBNF):
#
#   program     ::= statement* EOF
#   statement   ::= var_decl | assignment | print_stmt
#   var_decl    ::= 'let' IDENTIFIER '=' expression ';'
#   assignment  ::= IDENTIFIER '=' expression ';'
#   print_stmt  ::= 'print' expression ';'
#   expression  ::= term   (( '+' | '-' ) term   )*
#   term        ::= factor (( '*' | '/' ) factor )*
#   factor      ::= NUMBER | IDENTIFIER | '(' expression ')'
#
#  Example program (expected output: 50):
#
#    let x = 10;
#    let y = 20;
#    let result = x + y * 2;
#    print result;
# ══════════════════════════════════════════════════════════════════════════════


EXAMPLE_PROGRAM = """\
let x = 10;
let y = 20;
let result = x + y * 2;
print result;
"""


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 – LEXER  (Lexical Analyser)
# ══════════════════════════════════════════════════════════════════════════════

class TokenType:
    """Enumeration of every valid token type in MiniLang."""
    LET        = 'LET'
    PRINT      = 'PRINT'
    IDENTIFIER = 'IDENTIFIER'
    NUMBER     = 'NUMBER'
    EQUALS     = 'EQUALS'        # =
    PLUS       = 'PLUS'          # +
    MINUS      = 'MINUS'         # -
    MULTIPLY   = 'MULTIPLY'      # *
    DIVIDE     = 'DIVIDE'        # /
    LPAREN     = 'LPAREN'        # (
    RPAREN     = 'RPAREN'        # )
    SEMICOLON  = 'SEMICOLON'     # ;
    EOF        = 'EOF'


# Keywords recognised by the lexer
KEYWORDS = {
    'let':   TokenType.LET,
    'print': TokenType.PRINT,
}


class Token:
    """
    Represents a single lexical unit.

    Attributes:
        type  (str) : one of the TokenType constants
        value (any) : the literal value (string or int)
        line  (int) : source-line number (1-based), for error messages
    """

    def __init__(self, type_: str, value, line: int = 0):
        self.type  = type_
        self.value = value
        self.line  = line

    def __repr__(self):
        return f'Token({self.type}, {self.value!r}, line={self.line})'


class LexerError(Exception):
    pass


class Lexer:
    """
    Converts a raw source-code string into a flat list of Tokens.

    Usage:
        lexer  = Lexer(source)
        tokens = lexer.tokenize()
    """

    def __init__(self, source: str):
        self.source  = source          # full source text
        self.pos     = 0               # current character index
        self.line    = 1               # current line (for diagnostics)
        self.tokens  = []              # accumulated token list

    # ── helpers ──────────────────────────────────────────────────────────────

    def _current_char(self):
        """Return the character at the current position, or None at EOF."""
        return self.source[self.pos] if self.pos < len(self.source) else None

    def _advance(self):
        """Move the cursor forward by one character and track newlines."""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
        return ch

    def _peek(self, offset: int = 1):
        """Return the character `offset` positions ahead without consuming."""
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else None

    # ── scanning routines ────────────────────────────────────────────────────

    def _skip_whitespace(self):
        """Consume all whitespace (spaces, tabs, newlines) at current pos."""
        while self._current_char() is not None and self._current_char().isspace():
            self._advance()

    def _skip_comment(self):
        """Consume a single-line comment starting with '#'."""
        while self._current_char() is not None and self._current_char() != '\n':
            self._advance()

    def _read_number(self) -> Token:
        """
        Consume a sequence of digit characters and return a NUMBER token.
        Only integer literals are supported in MiniLang v1.
        """
        start_line = self.line
        buf = []
        while self._current_char() is not None and self._current_char().isdigit():
            buf.append(self._advance())
        return Token(TokenType.NUMBER, int(''.join(buf)), start_line)

    def _read_identifier_or_keyword(self) -> Token:
        """
        Consume an alphanumeric / underscore sequence.
        If the result matches a reserved keyword, emit the keyword token;
        otherwise emit an IDENTIFIER token.
        """
        start_line = self.line
        buf = []
        while self._current_char() is not None and (
            self._current_char().isalnum() or self._current_char() == '_'
        ):
            buf.append(self._advance())

        word = ''.join(buf)
        token_type = KEYWORDS.get(word, TokenType.IDENTIFIER)
        return Token(token_type, word, start_line)

    # ── public API ───────────────────────────────────────────────────────────

    def tokenize(self) -> list:
        """
        Drive the main scanning loop and return the full token list,
        always terminated by an EOF token.
        """
        # Map single characters to their token types
        single_char = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            ';': TokenType.SEMICOLON,
            '=': TokenType.EQUALS,
        }

        while self._current_char() is not None:
            ch = self._current_char()

            # ── whitespace ────────────────────────────────────────────────
            if ch.isspace():
                self._skip_whitespace()

            # ── single-line comment ───────────────────────────────────────
            elif ch == '#':
                self._skip_comment()

            # ── numeric literal ───────────────────────────────────────────
            elif ch.isdigit():
                self.tokens.append(self._read_number())

            # ── identifier or keyword ─────────────────────────────────────
            elif ch.isalpha() or ch == '_':
                self.tokens.append(self._read_identifier_or_keyword())

            # ── single-character operators & punctuation ──────────────────
            elif ch in single_char:
                self.tokens.append(
                    Token(single_char[ch], ch, self.line)
                )
                self._advance()

            else:
                raise LexerError(
                    f"Unexpected character {ch!r} at line {self.line}"
                )

        # Sentinel: parser reads this to know it has reached the end
        self.tokens.append(Token(TokenType.EOF, None, self.line))
        return self.tokens


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 – AST NODE DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

class ASTNode:
    """Base class for every node in the Abstract Syntax Tree."""


class Program(ASTNode):
    """
    Root node.  Holds an ordered list of top-level statements.
    """
    def __init__(self, statements: list):
        self.statements = statements          # list[ASTNode]

    def __repr__(self):
        return f'Program(statements={self.statements})'


class VarDecl(ASTNode):
    """
    Represents:  let <name> = <expr>;
    """
    def __init__(self, name: str, expr: ASTNode):
        self.name = name                      # str
        self.expr = expr                      # ASTNode (the right-hand side)

    def __repr__(self):
        return f'VarDecl(name={self.name!r}, expr={self.expr})'


class Assign(ASTNode):
    """
    Represents:  <name> = <expr>;
    """
    def __init__(self, name: str, expr: ASTNode):
        self.name = name
        self.expr = expr

    def __repr__(self):
        return f'Assign(name={self.name!r}, expr={self.expr})'


class Print(ASTNode):
    """
    Represents:  print <expr>;
    """
    def __init__(self, expr: ASTNode):
        self.expr = expr

    def __repr__(self):
        return f'Print(expr={self.expr})'


class BinOp(ASTNode):
    """
    Represents a binary arithmetic operation.

    Attributes:
        left  : left operand (ASTNode)
        op    : operator token ('+', '-', '*', '/')
        right : right operand (ASTNode)
    """
    def __init__(self, left: ASTNode, op: str, right: ASTNode):
        self.left  = left
        self.op    = op
        self.right = right

    def __repr__(self):
        return f'BinOp({self.left} {self.op} {self.right})'


class Number(ASTNode):
    """An integer literal node."""
    def __init__(self, value: int):
        self.value = value

    def __repr__(self):
        return f'Number({self.value})'


class Identifier(ASTNode):
    """A variable reference node."""
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f'Identifier({self.name!r})'


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 – PARSER  (Recursive Descent)
# ══════════════════════════════════════════════════════════════════════════════

class ParseError(Exception):
    pass


class Parser:
    """
    Converts a list of Tokens into an AST using recursive descent.

    Precedence (low → high):
      1. addition / subtraction      (expression)
      2. multiplication / division   (term)
      3. atom: number, identifier,   (factor)
               parenthesised expr

    Usage:
        parser = Parser(tokens)
        ast    = parser.parse()
    """

    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos    = 0                        # index of the current token

    # ── token-stream helpers ─────────────────────────────────────────────────

    def _current(self) -> Token:
        """Return the token under the cursor (never goes past EOF)."""
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        """Look ahead without consuming."""
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def _advance(self) -> Token:
        """Consume and return the current token, then move forward."""
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _expect(self, token_type: str) -> Token:
        """
        Consume the current token if it matches `token_type`;
        raise ParseError otherwise.
        """
        tok = self._current()
        if tok.type != token_type:
            raise ParseError(
                f"Expected {token_type} but got {tok.type} ({tok.value!r}) "
                f"at line {tok.line}"
            )
        return self._advance()

    def _match(self, *token_types: str) -> bool:
        """Return True (without consuming) if the current token is one of the given types."""
        return self._current().type in token_types

    # ── grammar rules ────────────────────────────────────────────────────────

    def parse(self) -> Program:
        """
        program ::= statement* EOF
        Entry point — returns the root Program node.
        """
        statements = []
        while not self._match(TokenType.EOF):
            statements.append(self._parse_statement())
        return Program(statements)

    def _parse_statement(self) -> ASTNode:
        """
        statement ::= var_decl | print_stmt | assignment
        Dispatches to the correct sub-parser by looking at the current token.
        """
        tok = self._current()

        if tok.type == TokenType.LET:
            return self._parse_var_decl()

        elif tok.type == TokenType.PRINT:
            return self._parse_print()

        elif tok.type == TokenType.IDENTIFIER:
            # Could be an assignment:  name = expr;
            return self._parse_assignment()

        else:
            raise ParseError(
                f"Unexpected token {tok.type} ({tok.value!r}) at line {tok.line}. "
                f"Expected a statement."
            )

    def _parse_var_decl(self) -> VarDecl:
        """
        var_decl ::= 'let' IDENTIFIER '=' expression ';'
        """
        self._expect(TokenType.LET)
        name_tok = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.EQUALS)
        expr = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return VarDecl(name_tok.value, expr)

    def _parse_assignment(self) -> Assign:
        """
        assignment ::= IDENTIFIER '=' expression ';'
        """
        name_tok = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.EQUALS)
        expr = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return Assign(name_tok.value, expr)

    def _parse_print(self) -> Print:
        """
        print_stmt ::= 'print' expression ';'
        """
        self._expect(TokenType.PRINT)
        expr = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return Print(expr)

    def _parse_expression(self) -> ASTNode:
        """
        expression ::= term (( '+' | '-' ) term)*

        Handles the lowest-precedence binary operators (+, -).
        Left-associative: a - b - c  ⟹  ((a - b) - c)
        """
        node = self._parse_term()

        while self._match(TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()          # consume '+' or '-'
            right  = self._parse_term()
            node   = BinOp(node, op_tok.value, right)

        return node

    def _parse_term(self) -> ASTNode:
        """
        term ::= factor (( '*' | '/' ) factor)*

        Handles higher-precedence binary operators (*, /).
        Left-associative: a / b / c  ⟹  ((a / b) / c)
        """
        node = self._parse_factor()

        while self._match(TokenType.MULTIPLY, TokenType.DIVIDE):
            op_tok = self._advance()          # consume '*' or '/'
            right  = self._parse_factor()
            node   = BinOp(node, op_tok.value, right)

        return node

    def _parse_factor(self) -> ASTNode:
        """
        factor ::= NUMBER | IDENTIFIER | '(' expression ')'

        Handles atoms and parenthesised sub-expressions.
        """
        tok = self._current()

        if tok.type == TokenType.NUMBER:
            self._advance()
            return Number(tok.value)

        elif tok.type == TokenType.IDENTIFIER:
            self._advance()
            return Identifier(tok.value)

        elif tok.type == TokenType.LPAREN:
            self._advance()                   # consume '('
            node = self._parse_expression()
            self._expect(TokenType.RPAREN)    # consume ')'
            return node

        else:
            raise ParseError(
                f"Unexpected token {tok.type} ({tok.value!r}) at line {tok.line}. "
                f"Expected a number, identifier, or '('."
            )


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 4 – BYTECODE INSTRUCTION DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

class OpCode:
    """
    All opcodes supported by the MiniLang virtual machine.

    Stack-based semantics:
        PUSH <val>    — push an integer constant onto the stack
        LOAD <name>   — push the value of a global variable
        STORE <name>  — pop top-of-stack and store it as a global variable
        ADD           — pop two values, push their sum
        SUB           — pop two values, push (second - top)
        MUL           — pop two values, push their product
        DIV           — pop two values, push (second // top)   [integer div]
        PRINT         — pop top value, print it
        HALT          — stop the VM
    """
    PUSH  = 'PUSH'
    LOAD  = 'LOAD'
    STORE = 'STORE'
    ADD   = 'ADD'
    SUB   = 'SUB'
    MUL   = 'MUL'
    DIV   = 'DIV'
    PRINT = 'PRINT'
    HALT  = 'HALT'


class Instruction:
    """
    A single bytecode instruction.

    Attributes:
        opcode   (str)        : one of the OpCode constants
        operand  (any | None) : optional argument (e.g. integer or variable name)
    """

    def __init__(self, opcode: str, operand=None):
        self.opcode  = opcode
        self.operand = operand

    def __repr__(self):
        if self.operand is not None:
            return f'{self.opcode:<8} {self.operand}'
        return self.opcode


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 4 – COMPILER  (AST → Bytecode)
# ══════════════════════════════════════════════════════════════════════════════

class CompileError(Exception):
    pass


class Compiler:
    """
    Walks the AST in a post-order traversal and emits bytecode instructions.

    The compiler keeps a list of `Instruction` objects — the "bytecode program".
    Each visit_* method appends instructions for one AST node type.

    Usage:
        compiler = Compiler()
        bytecode = compiler.compile(ast)   # returns list[Instruction]
    """

    def __init__(self):
        self.instructions = []             # accumulated bytecode

    # ── internal emit helper ─────────────────────────────────────────────────

    def _emit(self, opcode: str, operand=None):
        """Append one instruction to the output program."""
        self.instructions.append(Instruction(opcode, operand))

    # ── public API ───────────────────────────────────────────────────────────

    def compile(self, node: ASTNode) -> list:
        """
        Entry point.  Visits the Program node and finalises with HALT.
        Returns the completed list of Instruction objects.
        """
        self._visit(node)
        self._emit(OpCode.HALT)
        return self.instructions

    # ── visitor dispatch ─────────────────────────────────────────────────────

    def _visit(self, node: ASTNode):
        """
        Dynamic dispatch to the correct visit_* method.
        Maps node class name → method name.
        """
        method_name = f'_visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self._visit_unknown)
        visitor(node)

    def _visit_unknown(self, node: ASTNode):
        raise CompileError(f"No compilation rule for AST node: {type(node).__name__}")

    # ── node visitors ────────────────────────────────────────────────────────

    def _visit_Program(self, node: Program):
        """Visit every statement in order."""
        for stmt in node.statements:
            self._visit(stmt)

    def _visit_VarDecl(self, node: VarDecl):
        """
        let x = expr;
          → evaluate expr (leaves result on stack)
          → STORE x
        """
        self._visit(node.expr)               # push computed value
        self._emit(OpCode.STORE, node.name)  # pop and save

    def _visit_Assign(self, node: Assign):
        """
        x = expr;
          → same code shape as VarDecl (no runtime distinction needed)
        """
        self._visit(node.expr)
        self._emit(OpCode.STORE, node.name)

    def _visit_Print(self, node: Print):
        """
        print expr;
          → evaluate expr
          → PRINT
        """
        self._visit(node.expr)
        self._emit(OpCode.PRINT)

    def _visit_BinOp(self, node: BinOp):
        """
        Binary arithmetic — emit left, then right, then the operator.
        The stack machine pops the *top two* values, so evaluation order
        matters for SUB and DIV:
            left   is pushed first  → it becomes the 'second' value
            right  is pushed second → it becomes the 'top'
        The VM computes: second OP top  =  left OP right  ✓
        """
        self._visit(node.left)
        self._visit(node.right)

        op_map = {
            '+': OpCode.ADD,
            '-': OpCode.SUB,
            '*': OpCode.MUL,
            '/': OpCode.DIV,
        }
        opcode = op_map.get(node.op)
        if opcode is None:
            raise CompileError(f"Unknown binary operator: {node.op!r}")
        self._emit(opcode)

    def _visit_Number(self, node: Number):
        """Integer literal → PUSH its value."""
        self._emit(OpCode.PUSH, node.value)

    def _visit_Identifier(self, node: Identifier):
        """Variable reference → LOAD the variable's value onto the stack."""
        self._emit(OpCode.LOAD, node.name)


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 5 – VIRTUAL MACHINE
# ══════════════════════════════════════════════════════════════════════════════

class VMError(Exception):
    pass


class VM:
    """
    Stack-based virtual machine for MiniLang bytecode.

    Internal state:
        stack    (list[int])        : operand stack (grows to the right)
        globals  (dict[str, int])   : variable storage
        pc       (int)              : program counter (instruction index)
        program  (list[Instruction]): the bytecode to execute

    Usage:
        vm = VM(bytecode)
        vm.run()
    """

    def __init__(self, program: list):
        self.program = program
        self.stack   = []                  # operand stack
        self.globals = {}                  # variable name → integer value
        self.pc      = 0                   # program counter

    # ── stack helpers ─────────────────────────────────────────────────────────

    def _push(self, value: int):
        self.stack.append(value)

    def _pop(self) -> int:
        if not self.stack:
            raise VMError("Stack underflow — attempted to pop from an empty stack.")
        return self.stack.pop()

    # ── main execution loop ──────────────────────────────────────────────────

    def run(self):
        """
        Fetch-decode-execute loop.
        Reads one instruction per iteration, dispatches to the handler,
        and terminates when HALT is reached.
        """
        while self.pc < len(self.program):
            instr = self.program[self.pc]
            self.pc += 1                   # advance program counter *before* executing

            # ── PUSH ───────────────────────────────────────────────────────
            if instr.opcode == OpCode.PUSH:
                self._push(instr.operand)

            # ── LOAD ───────────────────────────────────────────────────────
            elif instr.opcode == OpCode.LOAD:
                var_name = instr.operand
                if var_name not in self.globals:
                    raise VMError(
                        f"Runtime Error: variable '{var_name}' is not defined."
                    )
                self._push(self.globals[var_name])

            # ── STORE ──────────────────────────────────────────────────────
            elif instr.opcode == OpCode.STORE:
                self.globals[instr.operand] = self._pop()

            # ── ADD ────────────────────────────────────────────────────────
            elif instr.opcode == OpCode.ADD:
                right = self._pop()
                left  = self._pop()
                self._push(left + right)

            # ── SUB ────────────────────────────────────────────────────────
            elif instr.opcode == OpCode.SUB:
                right = self._pop()
                left  = self._pop()
                self._push(left - right)

            # ── MUL ────────────────────────────────────────────────────────
            elif instr.opcode == OpCode.MUL:
                right = self._pop()
                left  = self._pop()
                self._push(left * right)

            # ── DIV ────────────────────────────────────────────────────────
            elif instr.opcode == OpCode.DIV:
                right = self._pop()
                left  = self._pop()
                if right == 0:
                    raise VMError("Runtime Error: division by zero.")
                self._push(left // right)  # integer division

            # ── PRINT ──────────────────────────────────────────────────────
            elif instr.opcode == OpCode.PRINT:
                value = self._pop()
                print(value)

            # ── HALT ───────────────────────────────────────────────────────
            elif instr.opcode == OpCode.HALT:
                break                      # clean termination

            else:
                raise VMError(f"Unknown opcode: {instr.opcode!r}")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 6 – EXECUTION PIPELINE  (main)
# ══════════════════════════════════════════════════════════════════════════════

def disassemble(bytecode: list):
    """
    Pretty-prints the compiled bytecode with instruction addresses.
    Useful for debugging and understanding code generation.
    """
    print("+------------------------------------------")
    print("|  DISASSEMBLY")
    print("+------------------------------------------")
    for idx, instr in enumerate(bytecode):
        print(f"|  {idx:>4}  {instr}")
    print("+------------------------------------------")


def run_pipeline(source: str, verbose: bool = True):
    """
    Full compiler pipeline: source text → output.

    Steps
    ─────
    1. Lex   : source  → token stream
    2. Parse : tokens  → AST
    3. Compile: AST    → bytecode
    4. Run   : bytecode → output
    """

    if verbose:
        print("=" * 50)
        print("  MiniLang Compiler & VM")
        print("=" * 50)
        print("\n-- Source Program --------------------------------")
        print(source.strip())
        print()

    # ── Step 1: Lex ──────────────────────────────────────────────────────────
    lexer  = Lexer(source)
    tokens = lexer.tokenize()

    if verbose:
        print("-- Tokens ----------------------------------------")
        for tok in tokens:
            print(f"   {tok}")
        print()

    # ── Step 2: Parse ────────────────────────────────────────────────────────
    parser = Parser(tokens)
    ast    = parser.parse()

    if verbose:
        print("-- Abstract Syntax Tree --------------------------")
        for node in ast.statements:
            print(f"   {node}")
        print()

    # ── Step 3: Compile ──────────────────────────────────────────────────────
    compiler = Compiler()
    bytecode = compiler.compile(ast)

    if verbose:
        disassemble(bytecode)
        print()

    # ── Step 4: Run ──────────────────────────────────────────────────────────
    if verbose:
        print("-- Program Output --------------------------------")

    vm = VM(bytecode)
    vm.run()

    if verbose:
        print()
        print("-- Final Variable State --------------------------")
        for name, val in vm.globals.items():
            print(f"   {name} = {val}")
        print("=" * 50)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Run the example program or a source file passed as a command-line argument.

    Usage:
        python minilang.py                # run the built-in example
        python minilang.py my_prog.ml     # run a .ml source file
    """
    if len(sys.argv) > 1:
        # Load source from file
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                source = f.read()
        except FileNotFoundError:
            print(f"Error: file not found: {filename}", file=sys.stderr)
            sys.exit(1)
    else:
        source = EXAMPLE_PROGRAM

    run_pipeline(source, verbose=True)


if __name__ == '__main__':
    main()
