"""Construa um CFG auxiliar por função, preservando os nós da AST."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from ast_nodes import Block, FunctionDecl, IfStmt, Stmt, WhileStmt, ReturnStmt
from cfg import BlockId, CFG, Jump, Branch, Return, ScopeExit


class CFGBuilder:
    def build(self, function: FunctionDecl) -> CFG:
        self.cfg = CFG(function)
        body_entry = self.cfg.new_block()
        self.cfg.terminate(self.cfg.entry, Jump(body_entry.id))
        continuation = self._build_block(function.body, body_entry.id)
        if continuation is not None:
            self.cfg.terminate(continuation, Jump(self.cfg.fallthrough_exit))
        return self.cfg

    def _build_block(self, block: Block, current: BlockId) -> BlockId | None:
        """Percorra um bloco da AST e devolva sua continuação normal."""
        # Processa cada comando do bloco sequencialmente
        for stmt in block.statements:
            if current is None:
                break # O caminho anterior terminou (ex: após um return)
            current = self._build_statement(stmt, current)

        # Se o bloco ainda tiver continuação, marcamos a saída do escopo
        if current is not None:
            scope = block.metadata.get("scope")
            if scope is not None:
                self.cfg.blocks[current].operations.append(ScopeExit(scope))

        return current

    def _build_statement(self, statement: Stmt, current: BlockId) -> BlockId | None:
        """incorpore um comando ao CFG e devolva sua continuação normal."""
        if isinstance(statement, Block):
            return self._build_block(statement, current)
        
        elif isinstance(statement, IfStmt):
            return self._build_if(statement, current)
            
        elif isinstance(statement, WhileStmt):
            return self._build_while(statement, current)
            
        elif isinstance(statement, ReturnStmt):
            # O retorno não possui sucessor normal, o ramo encerra aqui.
            self.cfg.terminate(current, Return(statement))
            return None
            
        else:
            # VarDecl, Assignment, CallStmt, PrintStmt permanecem no bloco básico
            self.cfg.blocks[current].operations.append(statement)
            return current

    def _build_if(self, statement: IfStmt, current: BlockId) -> BlockId | None:
        """construa o fluxo da condicional e devolva sua continuação."""
        true_block = self.cfg.new_block()
        false_block = self.cfg.new_block()
        join_block = self.cfg.new_block()

        # O bloco atual bifurca dependendo da condição
        self.cfg.terminate(current, Branch(statement.condition, true_block.id, false_block.id))

        # Constrói o ramo verdadeiro
        true_end = self._build_block(statement.then_block, true_block.id)
        if true_end is not None:
            self.cfg.terminate(true_end, Jump(join_block.id))

        # Constrói o ramo falso, se existir
        if statement.else_block is not None:
            false_end = self._build_block(statement.else_block, false_block.id)
        else:
            false_end = false_block.id
            
        if false_end is not None:
            self.cfg.terminate(false_end, Jump(join_block.id))

        # Se ambos os ramos encerram (ex: returns em ambos), não há continuação
        if true_end is None and false_end is None:
            return None

        return join_block.id

    def _build_while(self, statement: WhileStmt, current: BlockId) -> BlockId | None:
        """construa o fluxo do laço e devolva sua continuação."""
        header_block = self.cfg.new_block()
        body_block = self.cfg.new_block()
        exit_block = self.cfg.new_block()

        # O fluxo entra no cabeçalho do laço incondicionalmente
        self.cfg.terminate(current, Jump(header_block.id))
        
        # O cabeçalho decide se entra no corpo ou sai do laço
        self.cfg.terminate(header_block.id, Branch(statement.condition, body_block.id, exit_block.id))

        # Constrói o corpo do laço
        body_end = self._build_block(statement.body, body_block.id)
        if body_end is not None:
            # Ao fim do corpo, salta de volta para avaliar a condição
            self.cfg.terminate(body_end, Jump(header_block.id))

        return exit_block.id
