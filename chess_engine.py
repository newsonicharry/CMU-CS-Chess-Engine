import struct
import threading
import time
from time import sleep
from cmu_graphics import *
import array as arr
from enum import Enum
import random
from typing import Any, Generator
from collections import namedtuple
import base64
import zlib
import copy


# Chess engine built in python, based off my personal high performance chess engine in rust that performs above a
# world champion level  (https://github.com/newsonicharry/Rust-Chess-Engine)
# Utilizes magic bitboards for "fast" move generation
# (as fast as brython will allow anyway, this version of python seems to run many times slower than my local cpython)
# And a very compressed NNUE (Efficiently Updatable Nural Network) for the position evaluation


# GUI Initialization
# ----------------------------------------------------------------------------------------------------------------------
IN_CMU_EDITOR = False

if not IN_CMU_EDITOR:
    threading.Thread(target=cmu_graphics.run).start()
Rect(0, 0, 400, 400, fill=rgb(48, 46, 43))
LOADING_LABEL = Label("LOADING", 200, 200, size=24, fill=rgb(226, 226, 225), bold=True)
sleep(.01)


# Enums
# ----------------------------------------------------------------------------------------------------------------------


class Color(Enum):
    White = 0
    Black = 1

    def is_white(self):
        return self == Color.White

    def __invert__(self):
        match self:
            case Color.White: return Color.Black
            case Color.Black: return Color.White


class BasePiece(Enum):
    Pawn = 0
    Knight = 1
    Bishop = 2
    Rook = 3
    Queen = 4
    King = 5


class Piece(Enum):
    WhitePawn = 0
    WhiteKnight = 1
    WhiteBishop = 2
    WhiteRook = 3
    WhiteQueen = 4
    WhiteKing = 5
    BlackPawn = 6
    BlackKnight = 7
    BlackBishop = 8
    BlackRook = 9
    BlackQueen = 10
    BlackKing = 11
    NoPiece = 12

    @staticmethod
    def from_str(s: str):
        match s:
            case "P": return Piece.WhitePawn
            case "N": return Piece.WhiteKnight
            case "B": return Piece.WhiteBishop
            case "R": return Piece.WhiteRook
            case "Q": return Piece.WhiteQueen
            case "K": return Piece.WhiteKing
            case "p": return Piece.BlackPawn
            case "n": return Piece.BlackKnight
            case "b": return Piece.BlackBishop
            case "r": return Piece.BlackRook
            case "q": return Piece.BlackQueen
            case "k": return Piece.BlackKing
            case _:   return Piece.NoPiece

    @staticmethod
    def from_base_piece(base_piece: BasePiece, color: Color):
        offset = 6 if color == color.Black else 0
        return Piece(base_piece.value + offset)

    @classmethod
    def iter_white(cls):
        for piece_value in range(Piece.WhitePawn.value, Piece.WhiteKing.value+1):
            yield Piece(piece_value)

    @classmethod
    def iter_black(cls):
        for piece_value in range(Piece.BlackPawn.value, Piece.BlackKing.value+1):
            yield Piece(piece_value)


    def __str__(self):
        lookup = ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k", " "]
        return lookup[self.value]


    def color(self) -> Color:
        if self.value > 5:
            return Color.Black
        return Color.White

    def is_piece(self) -> bool:
        return self != Piece.NoPiece

    def is_pawn(self) -> bool:
        return self == Piece.WhitePawn or self == Piece.BlackPawn

    def is_king(self) -> bool:
        return self == Piece.WhiteKing or self == Piece.BlackKing



class File(Enum):
    A = 0
    B = 1
    C = 2
    D = 3
    E = 4
    F = 5
    G = 6
    H = 7

    def __str__(self):
        lookup = ["a", "b", "c", "d", "e", "f", "g", "h"]
        return lookup[self.value]


class Rank(Enum):
    First = 0
    Second = 1
    Third = 2
    Fourth = 3
    Fifth = 4
    Sixth = 5
    Seventh = 6
    Eighth = 7

    def is_pawn_start(self, color: Color) -> bool:
        match color:
            case Color.White:
                return self == Rank.Second
            case Color.Black:
                return self == Rank.Seventh

    def is_pawn_promotion(self, color: Color) -> bool:
        return self.is_pawn_start(~color)

    def __str__(self):
        return str(self.value + 1)

class Square(Enum):
    A1 = 0;B1 = 1;C1 = 2;D1 = 3;E1 = 4;F1 = 5;G1 = 6;H1 = 7;A2 = 8;B2 = 9;C2 = 10;D2 = 11;E2 = 12;F2 = 13;G2 = 14;H2 = 15;A3 = 16;B3 = 17;C3 = 18;D3 = 19;E3 = 20;F3 = 21;G3 = 22;H3 = 23;A4 = 24;B4 = 25;C4 = 26;D4 = 27;E4 = 28;F4 = 29;G4 = 30;H4 = 31;A5 = 32;B5 = 33;C5 = 34;D5 = 35;E5 = 36;F5 = 37;G5 = 38;H5 = 39;A6 = 40;B6 = 41;C6 = 42;D6 = 43;E6 = 44;F6 = 45;G6 = 46;H6 = 47;A7 = 48;B7 = 49;C7 = 50;D7 = 51;E7 = 52;F7 = 53;G7 = 54;H7 = 55;A8 = 56;B8 = 57;C8 = 58;D8 = 59;E8 = 60;F8 = 61;G8 = 62;H8 = 63

    def file(self) -> File:
        return File(self.value % 8)

    def rank(self) -> Rank:
        return Rank(self.value // 8)

    def mask(self) -> int:
        return 1 << self.value

    def flip_vert(self) -> int:
        return self.value ^ 56

    @staticmethod
    def from_file_rank(file: File, rank: Rank):
        return Square(file.value + rank.value * 8)

class MoveFlag(Enum):
    NoFlag = 0
    PromoteKnight = 1
    PromoteBishop = 2
    PromoteRook = 3
    PromoteQueen = 4
    DoubleJump = 5
    EnPassant = 6
    CastleShort = 7
    CastleLong = 8

    def is_promotion(self) -> bool:
        if 1 <= self.value <= 4:
            return True
        return False

    def promotion_piece(self, color: Color) -> Piece:
        match color:
            case color.White: return Piece(self.value)
            case color.Black: return Piece(self.value+6)

    def is_en_passant_capture(self) -> bool:
        return self == MoveFlag.EnPassant

    def is_castles(self) -> bool:
        return self == MoveFlag.CastleShort or self == MoveFlag.CastleLong





# Constants
# ----------------------------------------------------------------------------------------------------------------------

NUM_PIECES = 12
NUM_FILES = 8
NUM_SQUARES = 64
MAX_DEPTH = 256
INFINITY = 30000
PIECE_VALUES = [100, 300, 300, 500, 900, 10000, 100, 300, 300, 500, 900, 0]
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# Utils
# ----------------------------------------------------------------------------------------------------------------------

    
        


def lsb(mask: int) -> int:
    if mask == 0:
        return -1
    index = 0
    while (mask & 1) == 0:
        mask >>= 1
        index += 1
    return index


def pop(mask: int) -> int:
    least_significant = lsb(mask)
    mask ^= (1 << least_significant)
    return mask


def to_uint64(x: int) -> int:
    return x % (1 << 64)


def and64(a: int, b: int) -> int:
    ua = to_uint64(a)
    ub = to_uint64(b)

    hi_a, lo_a = divmod(ua, 1 << 32)
    hi_b, lo_b = divmod(ub, 1 << 32)

    hi = hi_a & hi_b
    lo = lo_a & lo_b

    result = (hi << 32) | lo
    return result 




def all_squares(mask: int) -> list[Square]:
    squares = []

    index = 0
    while mask > 0:
        if mask & 1:
            squares.append(Square(index))
        mask >>= 1
        index += 1
    return squares


# Data Classes
# ----------------------------------------------------------------------------------------------------------------------

class BitBoard():
    def __init__(self, low, high):
        self.low = low
        self.high = high
    
    def __and__(self, other):
        
        
                

class Move:
    __slots__ = ("start_square", "target_square", "move_flag")

    def __init__(self, start_square: Square, target_square: Square, move_flag: MoveFlag):
        self.start_square = start_square
        self.target_square = target_square
        self.move_flag = move_flag

    @classmethod
    def default(cls):
        return cls(Square(0), Square(0), MoveFlag(0))

    def __str__(self):
        start_file = self.start_square.file()
        target_file = self.target_square.file()

        start_rank = self.start_square.rank()
        target_rank = self.target_square.rank()

        promotion_piece = ""
        if self.move_flag.is_promotion():
            promotion_piece = self.move_flag.promotion_piece(Color.Black).__str__()

        final_str = start_file.__str__() + start_rank.__str__() + target_file.__str__() + target_rank.__str__() + promotion_piece
        return final_str

    def is_default(self):
        return self.start_square == self.target_square == Square.A1

class MoveList:
    __slots__ = "moves"

    def __init__(self):
        self.moves = []

    def add_moves(self, target_mask: int, start: Square, move_flag: MoveFlag):
        while target_mask != 0:
            target = Square(lsb(target_mask))

            self.moves.append(Move(start, target, move_flag))
            target_mask = pop(target_mask)

    def add_promotion_moves(self, target_mask: int, start: Square):
        while target_mask != 0:
            target = Square(lsb(target_mask))

            self.moves.append(Move(start, target, MoveFlag.PromoteQueen))
            self.moves.append(Move(start, target, MoveFlag.PromoteRook))
            self.moves.append(Move(start, target, MoveFlag.PromoteBishop))
            self.moves.append(Move(start, target, MoveFlag.PromoteKnight))

            target_mask = pop(target_mask)

    def order_moves(self, orderings: list[int]) -> None:
        # thanks stackoverflow
        self.moves = [x for _, x in reversed(sorted(zip(orderings, self.moves)))]

    def contains_move(self, move: Move) -> bool:
        for cur_move in self.moves:
            if cur_move == move:
                return True

        return False


MAX_PIECE_LEN = 10

class PieceList:
    def __init__(self, bitboard: int):
        self.piece_indexes = arr.array("I", [0] * MAX_PIECE_LEN)
        self.piece_count = 0
        self.map = arr.array("I", [0] * NUM_SQUARES)

        squares = all_squares(bitboard)

        for (i, square) in enumerate(squares):
            self.map[square.value] = i
            self.piece_indexes[i] = square.value

        self.piece_count = len(squares)

    def add_piece(self, square: Square):
        self.piece_indexes[self.piece_count] = square.value
        self.map[square.value] = self.piece_count
        self.piece_count += 1

    def remove_piece(self, square: Square):
        piece_index = self.map[square.value]

        self.piece_indexes[piece_index] = self.piece_indexes[self.piece_count-1]
        self.map[self.piece_indexes[piece_index]] = piece_index
        self.piece_count -= 1


    def move_piece(self, from_square: Square, to_square: Square):
        piece_index = self.map[from_square.value]
        self.piece_indexes[piece_index] = to_square.value
        self.map[to_square.value] = piece_index

    def count(self):
        return self.piece_count

    def indexes(self) -> Generator[int, Any, None]:
        for i in range(self.piece_count):
            yield self.piece_indexes[i]


# Zobrist
# ----------------------------------------------------------------------------------------------------------------------
class Zobrist:
    __slots__ = ["squares", "double_jump", "castling_rights", "side_to_move"]
    def __init__(self):
        self.squares = [[0] * NUM_SQUARES] * NUM_PIECES
        self.double_jump = [0] * NUM_FILES
        self.castling_rights = [0] * 4
        self.side_to_move = 0

        for piece_index in range(NUM_PIECES):
            for square_index in range(NUM_SQUARES):
                self.squares[piece_index][square_index] = random.getrandbits(64)

        for i in range(NUM_FILES):
            self.double_jump[i] = random.getrandbits(64)

        for i in range(4):
            self.castling_rights[i] = random.getrandbits(64)

        self.side_to_move = random.getrandbits(64)

    def square(self, piece: Piece, square: Square) -> int:
        return self.squares[piece.value][square.value]

    def short_castle(self, color: Color) -> int:
        match color:
            case Color.White: return self.castling_rights[0]
            case Color.Black: return self.castling_rights[2]

    def long_castle(self, color: Color) -> int:
        match color:
            case Color.White: return self.castling_rights[1]
            case Color.Black: return self.castling_rights[3]

    def pawn_jump(self, file: File):
        return self.double_jump[file.value]


ZOBRIST = Zobrist()

# Board State
# ----------------------------------------------------------------------------------------------------------------------

BoardState = namedtuple("BoardState", [
    "move",
    "captured",
    "half_move_clock",
    "castling_rights",
    "en_passant_file",
    "can_en_passant",
    "zobrist",
    "in_check"
], defaults=[Move.default(), Piece.NoPiece, 0, 0, File.A, False, 0, False] )


# Board
# ----------------------------------------------------------------------------------------------------------------------
SQUARE_MOVED_CASTLING = [13, 15, 15, 15, 12, 15, 15, 14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 7, 15, 15, 15, 3, 15, 15, 11]


class Board:
    def __init__(self, fen: str) -> None:
        self.occupancy = 0
        self.white_occupancy = 0
        self.black_occupancy = 0

        self.bitboards = arr.array("I", [0] * NUM_PIECES)
        self.piece_lists = [PieceList(0) for _ in range(NUM_PIECES)]
        self.piece_squares = arr.array("I", [Piece.NoPiece.value] * NUM_SQUARES)

        self.side_to_move = Color.White
        self.en_passant_file = File.A
        self.can_en_passant = False
        self.castling_rights = 0
        self.half_move_clock = 0

        self.zobrist = 0

        self.board_states = [BoardState() for _ in range(MAX_DEPTH)]
        self.cur_board_state = 0
        self.in_check = False

        self._parse_fen(fen)
        self._initialize_zobrist()
        self.update_occupancy()

    def _parse_fen(self, fen: str) -> None:
        split_fen = fen.split(" ")
        positional_data = split_fen[0]
        ranks = positional_data.split("/")

        for (rank_index, section) in enumerate(ranks[::-1]):
            cur_file = 0

            for item in section:
                if item.isdigit():
                    num_skipped_files = int(item)
                    cur_file += num_skipped_files
                else:
                    piece = Piece.from_str(item)
                    square = Square(rank_index * 8 + cur_file)
                    self._add_piece(piece, square)
                    cur_file += 1

        side_to_move_data = split_fen[1]
        if side_to_move_data == "b":
            self.side_to_move = Color.Black

        castling_data = split_fen[2]
        if "K" in castling_data:
            self.castling_rights |= 0b0001
        if "Q" in castling_data:
            self.castling_rights |= 0b0010
        if "k" in castling_data:
            self.castling_rights |= 0b0100
        if "q" in castling_data:
            self.castling_rights |= 0b1000

    def _initialize_zobrist(self):
        final_zobrist = 0

        squares_with_pieces = all_squares(self.occupancy)
        for square in squares_with_pieces:
            piece = self.piece_at(square)
            final_zobrist ^= ZOBRIST.squares[piece.value][square.value]

        if self.has_short_castle_rights(Color.White): final_zobrist ^= ZOBRIST.castling_rights[0]
        if self.has_long_castle_rights(Color.White): final_zobrist ^= ZOBRIST.castling_rights[1]
        if self.has_short_castle_rights(Color.Black): final_zobrist ^= ZOBRIST.castling_rights[2]
        if self.has_long_castle_rights(Color.Black): final_zobrist ^= ZOBRIST.castling_rights[3]

        if self.can_en_passant:
            final_zobrist ^= ZOBRIST.double_jump[self.en_passant_file.value]

        final_zobrist ^= ZOBRIST.side_to_move

        self.zobrist = final_zobrist



    def piece_at(self, square: Square) -> Piece:
        return Piece(self.piece_squares[square.value])

    def orthogonal_bitboard_them(self) -> int:
        match self.side_to_move:
            case Color.White: return self.bitboards[Piece.BlackRook.value] | self.bitboards[Piece.BlackQueen.value]
            case Color.Black: return self.bitboards[Piece.WhiteRook.value] | self.bitboards[Piece.WhiteQueen.value]

    def diagonal_bitboard_them(self) -> int:
        match self.side_to_move:
            case Color.Black: return self.bitboards[Piece.WhiteBishop.value] | self.bitboards[Piece.WhiteQueen.value]
            case Color.White: return self.bitboards[Piece.BlackBishop.value] | self.bitboards[Piece.BlackQueen.value]

    def bitboard(self, base_piece: BasePiece, color: Color) -> int:
        match color:
            case Color.White: return self.bitboards[base_piece.value]
            case Color.Black: return self.bitboards[base_piece.value+6]

    def bitboard_them(self, base_piece: BasePiece) -> int:
        return self.bitboard(base_piece, ~self.side_to_move)


    def bitboard_combined(self, piece: BasePiece) -> int:
        return self.bitboards[piece.value] | self.bitboards[piece.value + 6]


    def piece_list_us(self, base_piece: BasePiece) -> Generator[int, Any, None]:
        piece = Piece.from_base_piece(base_piece, self.side_to_move)
        return self.piece_lists[piece.value].indexes()


    def piece_list_them(self, base_piece: BasePiece) -> Generator[int, Any, None]:
        piece = Piece.from_base_piece(base_piece, ~self.side_to_move)
        return self.piece_lists[piece.value].indexes()


    def king_square(self, color: Color) -> Square:
        match color :
            case Color.White: return Square(next(self.piece_lists[Piece.WhiteKing.value].indexes()))
            case Color.Black: return Square(next(self.piece_lists[Piece.BlackKing.value].indexes()))



    def occupancy_us(self) -> int:
        match self.side_to_move:
            case Color.White: return self.white_occupancy
            case Color.Black: return self.black_occupancy



    def occupancy_them(self) -> int:
        match self.side_to_move:
            case Color.White: return self.black_occupancy
            case Color.Black: return self.white_occupancy


    def occupancy(self) -> int:
        return self.occupancy


    def side_to_move(self) -> Color:
        return self.side_to_move


    def en_passant_file(self) -> File | None:
        if self.can_en_passant:
            return self.en_passant_file

        return None


    def has_short_castle_rights(self, color: Color) -> bool:
        match color:
            case Color.White: return self.castling_rights & 0b0001 != 0
            case Color.Black: return self.castling_rights & 0b0100 != 0



    def has_long_castle_rights(self, color: Color) -> bool:
        match color:
            case Color.White: return self.castling_rights & 0b0010 != 0
            case Color.Black: return self.castling_rights & 0b1000 != 0


    def zobrist(self) -> int:
        return self.zobrist


    def past_board_states(self) -> list[BoardState] | None:
        if self.cur_board_state > 0:
            return self.board_states[0:self.cur_board_state]


        return None


    def half_move_clock(self) -> int:
        return self.half_move_clock

    def set_in_check(self, in_check: bool) -> None:
        self.in_check = in_check

    def in_check(self) -> bool:
        return self.in_check

    def update_occupancy(self):
        self.white_occupancy = 0
        self.black_occupancy = 0
        self.occupancy = 0

        for piece in Piece.iter_white():
            bitboard = self.bitboards[piece.value]
            self.white_occupancy |= bitboard
            self.occupancy |= bitboard

        for piece in Piece.iter_black():
            bitboard = self.bitboards[piece.value]
            self.black_occupancy |= bitboard
            self.occupancy |= bitboard



    def push_board_state(self, move: Move, captured: Piece):

        new_board_state = BoardState(move,
                                     captured,
                                     self.half_move_clock,
                                     self.castling_rights,
                                     self.en_passant_file,
                                     self.can_en_passant,
                                     self.zobrist,
                                     self.in_check)

        self.board_states[self.cur_board_state] = new_board_state
        self.cur_board_state += 1


    def _add_piece(self, piece: Piece, square: Square, increment_zobrist=True) -> None:
        self.bitboards[piece.value] |= square.mask()
        self.piece_squares[square.value] = piece.value
        self.piece_lists[piece.value].add_piece(square)

        if increment_zobrist:
            self.zobrist ^= ZOBRIST.square(piece, square)

    def _remove_piece(self, piece: Piece, square: Square, increment_zobrist=True) -> None:
        self.bitboards[piece.value] &= ~square.mask()
        self.piece_squares[square.value] = Piece.NoPiece.value
        self.piece_lists[piece.value].remove_piece(square)

        if increment_zobrist:
            self.zobrist ^= ZOBRIST.square(piece, square)

    def _move_piece(self, piece: Piece, start: Square, target: Square, increment_zobrist=True) -> None:
        self.bitboards[piece.value] &= ~start.mask()
        self.bitboards[piece.value] |= target.mask()

        self.piece_squares[start.value] = Piece.NoPiece.value
        self.piece_squares[target.value] = piece.value

        self.piece_lists[piece.value].move_piece(start, target)

        if increment_zobrist:
            self.zobrist ^= ZOBRIST.square(piece, start)
            self.zobrist ^= ZOBRIST.square(piece, target)



    def _apply_quiet(self, played: Move) -> None:
        self._move_piece(self.piece_at(played.start_square), played.start_square, played.target_square)


    def _apply_double_jump(self, played: Move) -> None:
        self.en_passant_file =  played.start_square.file()
        self.can_en_passant = True
        self.zobrist ^= ZOBRIST.pawn_jump(self.en_passant_file)
        self._apply_quiet(played)


    def _apply_short_castle(self) -> None:
        self.zobrist ^= ZOBRIST.short_castle(self.side_to_move)
        match self.side_to_move :
            case Color.White:
                self._move_piece(Piece.WhiteKing, Square.E1, Square.G1)
                self._move_piece(Piece.WhiteRook, Square.H1, Square.F1)

            case Color.Black:
                self._move_piece(Piece.BlackKing, Square.E8, Square.G8)
                self._move_piece(Piece.BlackRook, Square.H8, Square.F8)



    def _apply_long_castle(self) -> None:
        self.zobrist ^= ZOBRIST.long_castle(self.side_to_move)
        match self.side_to_move:
            case Color.White:
                self._move_piece(Piece.WhiteKing, Square.E1, Square.C1)
                self._move_piece(Piece.WhiteRook, Square.A1, Square.D1)

            case Color.Black:
                self._move_piece(Piece.BlackKing, Square.E8, Square.C8)
                self._move_piece(Piece.BlackRook, Square.A8, Square.D8)




    def _apply_promotion(self, played: Move) -> None:
        self._remove_piece(self.piece_at(played.start_square), played.start_square)
        self._add_piece(played.move_flag.promotion_piece(self.side_to_move), played.target_square)



    def _apply_en_passant(self, played: Move) -> None:
        self._apply_quiet(played)

        match self.side_to_move:
            case Color.White: self._remove_piece(Piece.BlackPawn, Square(self.en_passant_file.value + 32))
            case Color.Black: self._remove_piece(Piece.WhitePawn, Square(self.en_passant_file.value + 24))



    def _reverse_quiet(self, played: Move) -> None:
        target = played.target_square
        self._move_piece(self.piece_at(target), target, played.start_square, increment_zobrist=False)


    def _reverse_short_castle(self) -> None:
        match self.side_to_move:
            case Color.White:
                self._move_piece(Piece.WhiteKing, Square.G1, Square.E1, increment_zobrist=False)
                self._move_piece(Piece.WhiteRook, Square.F1, Square.H1, increment_zobrist=False)

            case Color.Black:
                self._move_piece(Piece.BlackKing, Square.G8, Square.E8, increment_zobrist=False)
                self._move_piece(Piece.BlackRook, Square.F8, Square.H8, increment_zobrist=False)



    def _reverse_long_castle(self) -> None:
        match self.side_to_move:
            case Color.White:
                self._move_piece(Piece.WhiteKing, Square.C1, Square.E1, increment_zobrist=False)
                self._move_piece(Piece.WhiteRook, Square.D1, Square.A1, increment_zobrist=False)

            case Color.Black:
                self._move_piece(Piece.BlackKing, Square.C8, Square.E8, increment_zobrist=False)
                self._move_piece(Piece.BlackRook, Square.D8, Square.A8, increment_zobrist=False)




    def _reverse_promotion(self, played: Move):
        self._remove_piece(self.piece_at(played.target_square), played.target_square, increment_zobrist=False)

        original_pawn = Piece.BlackPawn
        if self.side_to_move.is_white():
            original_pawn = Piece.WhitePawn

        self._add_piece(original_pawn, played.start_square, increment_zobrist=False)


    def _reverse_en_passant(self, played: Move) -> None:
        self._reverse_quiet(played)

        match self.side_to_move:
            case Color.White: self._add_piece(Piece.BlackPawn, Square(self.en_passant_file.value + 32), increment_zobrist=False)
            case Color.Black: self._add_piece(Piece.WhitePawn, Square(self.en_passant_file.value + 24), increment_zobrist=False)


    def make_move(self, played: Move) -> None:

        start = played.start_square
        target = played.target_square
        capture = self.piece_at(target)
        moving_piece = self.piece_at(start)

        self.push_board_state(played, capture)

        self.can_en_passant = False
        if capture.is_piece():
            self._remove_piece(capture, target)


        if moving_piece.is_pawn() or capture.is_piece():
            self.half_move_clock = 0
        else:
            self.half_move_clock += 1

        self.castling_rights &= SQUARE_MOVED_CASTLING[start.value]
        self.castling_rights &= SQUARE_MOVED_CASTLING[target.value]

        match played.move_flag:
            case MoveFlag.NoFlag: self._apply_quiet(played),
            case MoveFlag.DoubleJump: self._apply_double_jump(played),
            case MoveFlag.CastleShort: self._apply_short_castle(),
            case MoveFlag.CastleLong: self._apply_long_castle(),
            case MoveFlag.EnPassant: self._apply_en_passant(played),
            case _: self._apply_promotion(played),


        self.side_to_move = ~self.side_to_move
        self.zobrist ^= ZOBRIST.side_to_move
        self.update_occupancy()


    def undo_move(self) -> None:
        last_board_state = self.board_states[self.cur_board_state-1]
        last_played = last_board_state.move

        self.castling_rights = last_board_state.castling_rights
        self.en_passant_file = last_board_state.en_passant_file
        self.can_en_passant = last_board_state.can_en_passant
        self.half_move_clock = last_board_state.half_move_clock
        self.zobrist = last_board_state.zobrist
        self.in_check = last_board_state.in_check

        self.side_to_move = ~self.side_to_move

        match last_played.move_flag:
            case MoveFlag.NoFlag: self._reverse_quiet(last_played),
            case MoveFlag.DoubleJump: self._reverse_quiet(last_played),
            case MoveFlag.CastleShort: self._reverse_short_castle(),
            case MoveFlag.CastleLong: self._reverse_long_castle(),
            case MoveFlag.EnPassant: self._reverse_en_passant(last_played),
            case _: self._reverse_promotion(last_played),



        if last_board_state.captured.is_piece() and not last_played.move_flag.is_en_passant_capture():
            self._add_piece(last_board_state.captured, last_played.target_square, increment_zobrist=False)


        self.cur_board_state -= 1


    
    

    def __str__(self) -> str:
        pretty_print = ""

        for i in range(NUM_SQUARES):
            if i % 8 == 0:
                pretty_print += "\n"

            square = i ^ 56

            piece = self.piece_at(Square(square))

            if piece == Piece.NoPiece:
                pretty_print += " . "
            else:
                pretty_print += f" {piece.__str__()} "

        return pretty_print


# Precomputed data
# ----------------------------------------------------------------------------------------------------------------------

KNIGHT_DIRECTIONS = [(-2, 1), (-1, 2), (1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1)]
BISHOP_DIRECTIONS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_DIRECTIONS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
KING_DIRECTIONS = [(-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0)]

WHITE_PAWN_ATTACKS_DIRECTIONS = [(1, 1), (-1, 1)]
BLACK_PAWN_ATTACKS_DIRECTIONS = [(1, -1), (-1, -1)]


def create_static_mask(directions: list[tuple[int, int]], square: Square) -> int:
    mask = 0

    x_cord = square.file().value
    y_cord = square.rank().value

    for direction in directions:
        x_dir, y_dir = direction

        new_x = x_cord + x_dir
        new_y = y_dir + y_cord

        if (new_x > 7 or new_x < 0) or (new_y > 7 or new_y < 0):
            continue

        new_square = Square.from_file_rank(File(new_x), Rank(new_y)).value

        mask |= 1 << new_square

    return mask


def create_dynamic_mask(directions: list[tuple[int, int]], square: Square, no_edge: bool) -> int:
    mask = 0

    for direction in directions:
        (x_dir, y_dir) = direction

        x_cord = square.file().value
        y_cord = square.rank().value

        while True:
            new_x = x_cord + x_dir
            new_y = y_cord + y_dir

            if (new_x > 7 or new_x < 0) or (new_y > 7 or new_y < 0):
                break

            if no_edge and ((x_dir != 0 and (new_x > 6 or new_x < 1)) or (y_dir != 0 and (new_y > 6 or new_y < 1))):
                break

            new_square = Square.from_file_rank(File(new_x), Rank(new_y)).value
            mask |= 1 << new_square

            x_cord = new_x
            y_cord = new_y
    return mask


class MovementMasks:
    def __init__(self) -> None:
        self.knight = arr.array("I", [0] * NUM_SQUARES)
        self.bishop = arr.array("I", [0] * NUM_SQUARES)
        self.rook = arr.array("I", [0] * NUM_SQUARES)
        self.king = arr.array("I", [0] * NUM_SQUARES)

        self._white_pawn_move = arr.array("I", [0] * NUM_SQUARES)
        self._black_pawn_move = arr.array("I", [0] * NUM_SQUARES)
        self._white_pawn_attack = arr.array("I", [0] * NUM_SQUARES)
        self._black_pawn_attack = arr.array("I", [0] * NUM_SQUARES)
        self._white_double_jump = arr.array("I", [0] * NUM_SQUARES)
        self._black_double_jump = arr.array("I", [0] * NUM_SQUARES)

        for i in range(NUM_SQUARES):
            square = Square(i)
            rank = square.rank()

            if rank.is_pawn_start(Color.White):
                self._white_double_jump[i] = 1 << (i + 16)

            if rank.is_pawn_start(Color.Black):
                self._black_double_jump[i] = 1 << (i - 16)

            if not rank == Rank.Eighth:
                self._white_pawn_move[i] = 1 << (i + 8)

            if not rank == Rank.First:
                self._black_pawn_move[i] = 1 << (i - 8)

            self._white_pawn_attack[i] |= create_static_mask(WHITE_PAWN_ATTACKS_DIRECTIONS, square)
            self._black_pawn_attack[i] |= create_static_mask(BLACK_PAWN_ATTACKS_DIRECTIONS, square)


            self.knight[i] = create_static_mask(KNIGHT_DIRECTIONS, square)
            self.king[i] = create_static_mask(KING_DIRECTIONS, square)

            self.bishop[i] = create_dynamic_mask(BISHOP_DIRECTIONS, square, False)
            self.rook[i] = create_dynamic_mask(ROOK_DIRECTIONS, square, False)

    def pawn_attacks(self, color: Color, square: Square) -> int:
        match color:
            case Color.White:
                return self._white_pawn_attack[square.value]
            case Color.Black:
                return self._black_pawn_attack[square.value]

    def pawn_move(self, color: Color, square: Square) -> int:
        match color:
            case Color.White:
                return self._white_pawn_move[square.value]
            case Color.Black:
                return self._black_pawn_move[square.value]

    def pawn_jump(self, color: Color, square: Square) -> int:
        match color:
            case Color.White:
                return self._white_double_jump[square.value]
            case Color.Black:
                return self._black_double_jump[square.value]

U64_MASK = 0xFFFFFFFFFFFFFFFF
# Magics are hardcoded for faster startup time, though is not necessary
# Simply deleting the variables will cause it to be computed at startup
BISHOP_MAGICS = arr.array("I", [11267898244874753, 289501447060480000, 9227878936644534296, 3461615023485354016, 1148028119978496, 287110242242560, 5774887991218552833, 364952102876889108, 9223442532317532928, 2305895897575260196, 37726445456359680, 1729386676465238112, 1801446456876367873, 19184433771317384, 558622712080, 4755801485685600272, 11675627251511134208, 81064819196821664, 16251248193226957312, 11538292665624043521, 3171097104812736576, 4611721211398070272, 4613375075537395712, 13873373845085490176, 4855447911825920, 2894190019641480, 4637599325684277312, 9241405402006962304, 2342576043699216385, 10421482371026059392, 1172066201086787858, 563577052741888, 580559890817027, 92407509864677664, 1691091866814464, 72341270253011072, 18032128679870848, 292753769672867968, 9730695085704192, 1441715381004799504, 1143569675470848, 13589972577749250, 9800184908303306752, 8071577257061253632, 1157426341486793474, 10377428789398339844, 577665819480474624, 4505972076708544, 9223805313425867784, 576817157297405953, 9802086792433239040, 72198404679663650, 37401196234819, 2885122943958975492, 3463303377344284704, 9225100766593810440, 364870880819414016, 2817506263834624, 18150540321088, 4521471020913664, 1369675585849673792, 309059662002520256, 1143509562426368, 9015998577410560])
BISHOP_SHIFTS = arr.array("I", [58, 59, 59, 59, 59, 59, 59, 58, 59, 59, 59, 59, 59, 59, 59, 59, 59, 59, 57, 57, 57, 57, 59, 59, 59, 59, 57, 55, 55, 57, 59, 59, 59, 59, 57, 55, 55, 57, 59, 59, 59, 59, 57, 57, 57, 57, 59, 59, 59, 59, 59, 59, 59, 59, 59, 59, 58, 59, 59, 59, 59, 59, 59, 58])
ROOK_MAGICS = arr.array("I", [36028936606466056, 4629718009660063744, 216191336375320640, 324311951876816900, 1297038891781988368, 2918351267422011904, 108087490736312448, 144126186490987276, 1306184632647192864, 16249057859194585153, 324962929334027400, 577023981566104064, 72198640764190848, 289497563336279040, 9332303179812962816, 1901222734487109760, 18023744370909312, 7498493655523549184, 9226469361567408128, 144126183730184256, 1155314591731812352, 576602039581213696, 4918498141358543361, 6918824252349350595, 1765481424821428352, 18049593623183492, 864726314983100416, 2306036527556788258, 2251872828719173, 2894688936445214976, 5480881897566507080, 4755801764851106819, 70375195017248, 5779308018671616, 281750139838464, 141905744627712, 4529990062310400, 111466291956548608, 149260928330793232, 566969237601, 4611721762219524100, 198228752885383296, 4625198054302056496, 301745714815369224, 576469548681723972, 1688884509802532, 3603188733419192456, 2885673652715532, 360781556220160, 9223477658837319744, 1171234970815987840, 144396800760088832, 144405461303820416, 2378463570653872640, 1176566536791000064, 708182130360832, 576532225399462402, 1152940885659353345, 9288743487834183, 434614956563374337, 144396697413370381, 576742253187039243, 162428679803633820, 1189135303592446978])
ROOK_SHIFTS = arr.array("I", [52, 53, 53, 53, 53, 53, 53, 52, 53, 54, 54, 54, 54, 54, 54, 53, 53, 54, 54, 54, 54, 54, 54, 53, 53, 54, 54, 54, 54, 54, 54, 53, 53, 54, 54, 54, 54, 54, 54, 53, 53, 54, 54, 54, 54, 54, 54, 53, 53, 54, 54, 54, 54, 54, 54, 53, 52, 53, 53, 53, 53, 53, 53, 52])

class SliderLookup:
    def __init__(self, num_entries: int, slider_type: BasePiece) -> None:
        self.flat_table = arr.array("I", [0] * num_entries)
        self.offsets = arr.array("I", [0] * num_entries)

        self.shifts = arr.array("I", [0] * NUM_SQUARES)
        self.magics = arr.array("I", [0] * NUM_SQUARES)

        self.no_edge_masks = arr.array("I", [0] * NUM_SQUARES)

        direction = None
        match slider_type:
            case BasePiece.Rook:
                direction = ROOK_DIRECTIONS
            case BasePiece.Bishop:
                direction = BISHOP_DIRECTIONS

        for i in range(NUM_SQUARES):
            self.no_edge_masks[i] = create_dynamic_mask(direction, Square(i), True)

        if slider_type == BasePiece.Bishop and "BISHOP_MAGICS" in globals() and "BISHOP_SHIFTS" in globals():
            self.magics = BISHOP_MAGICS
            self.shifts = BISHOP_SHIFTS
        elif slider_type == BasePiece.Rook and "ROOK_MAGICS" in globals() and "ROOK_SHIFTS" in globals():
            self.magics = ROOK_MAGICS
            self.shifts = ROOK_SHIFTS
        else:
            for i in range(NUM_SQUARES):
                magic, shift = self._find_magic_and_shift(Square(i))
                self.magics[i] = magic
                self.shifts[i] = shift

        self._generate_move_lookup(slider_type)


    def _generate_move_lookup(self, slider_type: BasePiece):
        last_offset = 0

        for (piece_index, piece_move_mask) in enumerate(self.no_edge_masks):
            print(f"{piece_index}/63")
            square = Square(piece_index)
            blockers = self._generate_blockers(square)

            num_blockers = piece_move_mask.bit_count()
            blocker_combinations = 1 << num_blockers

            for blocker in blockers:
                magic = self.magics[piece_index]
                shift = self.shifts[piece_index]
                key = ((blocker*magic) & U64_MASK) >> shift

                valid_moves = self._get_moves_from_blockers(square, slider_type, blocker)
                self.flat_table[key+last_offset] = valid_moves

            self.offsets[piece_index] = last_offset
            last_offset += blocker_combinations

    @staticmethod
    def _get_moves_from_blockers(square: Square, slider_type: BasePiece, blockers: int) -> int:
        direction = None
        match slider_type:
            case BasePiece.Rook:
                direction = ROOK_DIRECTIONS
            case BasePiece.Bishop:
                direction = BISHOP_DIRECTIONS

        new_movement_mask = 0

        for direction in direction:
            x_dir, y_dir = direction

            x_pos = square.file().value
            y_pos = square.rank().value

            directional_move_mask = 0

            while True:
                x_pos += x_dir
                y_pos += y_dir

                if (x_pos > 7 or x_pos < 0) or (y_pos > 7 or y_pos < 0):
                    break

                new_square = Square.from_file_rank(File(x_pos), Rank(y_pos))

                directional_move_mask |= new_square.mask()

                test_x = x_pos + x_dir
                test_y = y_pos + y_dir
                end_of_board = (test_x > 7 or test_x < 0) or (test_y > 7 or test_y < 0)

                if directional_move_mask & blockers != 0 or end_of_board:
                    new_movement_mask |= directional_move_mask
                    break

        return new_movement_mask


    def _generate_blockers(self, square: Square) -> list[int]:
        no_edge_mask = self.no_edge_masks[square.value]
        squares = all_squares(no_edge_mask)
        total_blocker_patters = 1 << len(squares)
        all_blocker_patterns = [0] * total_blocker_patters

        for pattern_index in range(total_blocker_patters):
            for square_index in range(len(squares)):
                bit = (pattern_index >> square_index) & 1
                current_move = squares[square_index]

                all_blocker_patterns[pattern_index] |= (bit << current_move.value)


        return all_blocker_patterns


    def _find_magic_and_shift(self, square: Square) -> tuple[int, int]:
        no_edge_mask = self.no_edge_masks[square.value]
        num_blockers = no_edge_mask.bit_count()
        blockers = self._generate_blockers(square)

        shift = 64 - num_blockers

        while True:
            all_keys = set()

            magic = random.getrandbits(64) & random.getrandbits(64) & random.getrandbits(64)

            for blocker in blockers:
                new_key = ((blocker * magic) & U64_MASK) >> shift

                if new_key not in all_keys:
                    all_keys.add(new_key)
                else:
                    break

            if len(all_keys) == len(blockers):
                final_magic = magic
                break

        return final_magic, shift

    def get(self, square: Square, occupied: int) -> int:
        magic = self.magics[square.value]
        shift = self.shifts[square.value]
        blockers = self.no_edge_masks[square.value] & occupied

        key = ((magic * blockers) & U64_MASK) >> shift
        offset = self.offsets[square.value]

        return self.flat_table[key+offset]

class InBetween:
    def __init__(self) -> None:
        self.in_between = [[0 for _ in range(NUM_SQUARES)] for _ in range(NUM_SQUARES)]
        self._generate()

    def _generate(self):

         for i in range(NUM_SQUARES):
            start_square = Square(i)

            for j in range(NUM_SQUARES):
                target_square = Square(j)


                start_x = start_square.file()
                target_x = target_square.file()

                start_y = start_square.rank()
                target_y = target_square.rank()

                direction = (0 , 0)

                # could combine these but im trying to avoid a criminal amount of nesting
                # orthogonal
                if (start_x.value == target_x.value) and (start_y.value < target_y.value): direction = (0, 1)
                if (start_x.value == target_x.value) and (start_y.value > target_y.value): direction = (0, -1)
                if (start_y.value == target_y.value) and (start_x.value < target_x.value): direction = (1, 0)
                if (start_y.value == target_y.value) and (start_x.value > target_x.value): direction = (-1, 0)


                dif_x =  target_x.value - start_x.value
                dif_y = target_y.value - start_y.value
                # is a diagonal if the x and y parts of the triangle are the same (45 45 90 triangle)
                is_diagonal = abs(dif_x) == abs(dif_y)

                # diagonal
                if is_diagonal and (dif_x > 0) and (dif_y > 0): direction = (1, 1)
                if is_diagonal and (dif_x < 0)  and (dif_y > 0): direction = (-1, 1)
                if is_diagonal and (dif_x > 0) and (dif_y < 0):  direction = (1, -1)
                if is_diagonal and (dif_x < 0)  and (dif_y < 0):  direction = (-1, -1)


                if direction == (0, 0):
                    continue

                cur_x = (start_x.value + direction[0])
                cur_y = (start_y.value + direction[1])
                while (cur_x != target_x.value) or (cur_y != target_y.value):
                    file = File(cur_x)
                    rank = Rank(cur_y)

                    new_square = Square.from_file_rank(file, rank)

                    self.in_between[i][j] |= new_square.mask()

                    cur_x = (cur_x + direction[0])
                    cur_y = (cur_y + direction[1])



IN_BETWEEN = InBetween()
MOVEMENT_MASKS = MovementMasks()
BISHOP_LOOKUP = SliderLookup(5248, BasePiece.Bishop)
ROOK_LOOKUP = SliderLookup(102400, BasePiece.Rook)

def slider_lookup(piece: BasePiece, square: Square, occupancy: int) -> int | None:
    match piece:
        case BasePiece.Rook: return ROOK_LOOKUP.get(square, occupancy)
        case BasePiece.Bishop: return BISHOP_LOOKUP.get(square, occupancy)
        case BasePiece.Queen: return BISHOP_LOOKUP.get(square, occupancy) | ROOK_LOOKUP.get(square, occupancy)

    return None


# Move generation
# ----------------------------------------------------------------------------------------------------------------------
MAX_64_BIT_NUM = (1 << 64) - 1


class MoveGenerator:
    def generator(self, board: Board) -> MoveList:
        move_list = MoveList()

        board.update_occupancy()
        pieces_checking, allowed_squares = self._get_check_data(board)

        pin_ray_mask = [MAX_64_BIT_NUM] * NUM_SQUARES
        pinned_pieces_mask = self._get_pins(board, pin_ray_mask)

        if pieces_checking != 0:
            board.set_in_check(True)
        else:
            board.set_in_check(False)

        self._update_pawn_moves(board, move_list, allowed_squares, pin_ray_mask)
        self._update_knight_moves(board, move_list, allowed_squares, pinned_pieces_mask)

        self._update_king_moves(board, move_list, pieces_checking)

        self._update_slider_moves(BasePiece.Bishop, board, move_list, allowed_squares, pin_ray_mask)
        self._update_slider_moves(BasePiece.Rook, board, move_list, allowed_squares, pin_ray_mask)
        self._update_slider_moves(BasePiece.Queen, board, move_list, allowed_squares, pin_ray_mask)

        return move_list

    @staticmethod
    def _get_enemy_attacks(board: Board) -> int:

        attack_mask = 0

        all_pieces_no_king = board.occupancy & ~board.king_square(board.side_to_move).mask()

        for pawn_square in board.piece_list_them(BasePiece.Pawn):
            attack_mask |=  MOVEMENT_MASKS.pawn_attacks(~board.side_to_move, Square(pawn_square))


        for knight_square in board.piece_list_them(BasePiece.Knight):
            attack_mask |= MOVEMENT_MASKS.knight[knight_square]


        for bishop_square in board.piece_list_them(BasePiece.Bishop):
            attack_mask |= BISHOP_LOOKUP.get(Square(bishop_square), all_pieces_no_king)


        for rook_square in board.piece_list_them(BasePiece.Rook):
            attack_mask |= ROOK_LOOKUP.get(Square(rook_square), all_pieces_no_king)


        for queen_square in board.piece_list_them(BasePiece.Queen):
            attack_mask |=  slider_lookup(BasePiece.Queen, Square(queen_square), all_pieces_no_king)


        for king_square in board.piece_list_them(BasePiece.King):
            attack_mask |= MOVEMENT_MASKS.king[king_square]


        return attack_mask




    @staticmethod
    def _get_check_data(board: Board) -> tuple[int, int]:

        king_square = board.king_square(board.side_to_move)

        enemy_orthogonal = board.orthogonal_bitboard_them()
        enemy_diagonal = board.diagonal_bitboard_them()

        knight_checks = MOVEMENT_MASKS.knight[king_square.value] & board.bitboard_them(BasePiece.Knight)
        pawn_checks = MOVEMENT_MASKS.pawn_attacks(board.side_to_move, king_square) & board.bitboard_them(BasePiece.Pawn)

        regular_check = knight_checks | pawn_checks
        orthogonal_check = ROOK_LOOKUP.get(king_square, board.occupancy) & enemy_orthogonal
        diagonal_check = BISHOP_LOOKUP.get(king_square, board.occupancy) & enemy_diagonal


        all_checks = orthogonal_check | diagonal_check | regular_check
        allowed_squares = 0

        if all_checks.bit_count() == 1:
            index = lsb(all_checks)
            allowed_squares = IN_BETWEEN.in_between[king_square.value][index] | (1 << index)


        if all_checks == 0:
            allowed_squares = MAX_64_BIT_NUM


        return all_checks, allowed_squares


    @staticmethod
    def _update_pawn_moves(board: Board, move_list: MoveList, allowed_squares: int, pin_ray_mask: list[int]) -> None:

        king_square = board.king_square(board.side_to_move)

        for square_index in board.piece_list_us(BasePiece.Pawn):
            square = Square(square_index)

            pin_mask = pin_ray_mask[square_index]
            pawn_attacks = and64(MOVEMENT_MASKS.pawn_attacks(board.side_to_move, square), board.occupancy_them()) & allowed_squares & pin_mask
            pawn_moves = and64(MOVEMENT_MASKS.pawn_move(board.side_to_move, square), (~board.occupancy)) & allowed_squares & pin_mask
            double_jump = and64(MOVEMENT_MASKS.pawn_jump(board.side_to_move, square), (~board.occupancy))  & allowed_squares & pin_mask

            pawn_mask = square.mask()

            # en passant
            en_passant_file = board.en_passant_file
            if board.can_en_passant and pin_mask == MAX_64_BIT_NUM:
                en_passant_attack_mask = 1 << (en_passant_file.value + 40) if board.side_to_move.is_white() else 1<< (en_passant_file.value +16)
                attack_square_mask = MOVEMENT_MASKS.pawn_attacks(board.side_to_move, square) & en_passant_attack_mask
                # en passant discovered check
                if attack_square_mask != 0:
                    enemy_pawn_mask = 1 << (en_passant_file.value + 32) if board.side_to_move.is_white() else  1<< (en_passant_file.value +24)
                    new_blockers = board.occupancy & (~enemy_pawn_mask) & (~pawn_mask) | attack_square_mask

                    enemy_orthogonal = board.orthogonal_bitboard_them()
                    enemy_diagonal = board.diagonal_bitboard_them()

                    new_king_orthogonal_ray = ROOK_LOOKUP.get(king_square, new_blockers) & enemy_orthogonal
                    new_king_diagonal_ray = BISHOP_LOOKUP.get(king_square, new_blockers) & enemy_diagonal

                    if new_king_orthogonal_ray == 0 and new_king_diagonal_ray == 0:

                        move_list.add_moves(attack_square_mask, square, MoveFlag.EnPassant)


            # promotion
            if square.rank().is_pawn_promotion(board.side_to_move):
                move_list.add_promotion_moves(pawn_moves, square)
                move_list.add_promotion_moves(pawn_attacks, square)

                continue


            move_list.add_moves(pawn_attacks, square, MoveFlag.NoFlag)

            # normal moves and captures
            move_list.add_moves(pawn_moves, square, MoveFlag.NoFlag)

            # pawn double jump
            no_piece_in_way = MOVEMENT_MASKS.pawn_move(board.side_to_move, square) & (~board.occupancy) != 0
            if square.rank().is_pawn_start(board.side_to_move) and no_piece_in_way:
                move_list.add_moves(double_jump, square, MoveFlag.DoubleJump)


    @staticmethod
    def _update_knight_moves(board: Board, move_list: MoveList, allowed_squares: int, pinned_pieces_mask: int) -> None:

        for square_index in board.piece_list_us(BasePiece.Knight) :
            square = Square(square_index)

            if pinned_pieces_mask & square.mask() != 0:
                continue


            knight_moves = and64((MOVEMENT_MASKS.knight[square_index]), ~board.occupancy_us()) & allowed_squares

            move_list.add_moves(knight_moves, square, MoveFlag.NoFlag)



    @staticmethod
    def _update_slider_moves(slider_type: BasePiece, board: Board, move_list: MoveList, allowed_squares: int, pin_ray_mask: list[int]) -> None:
        for square_index in  board.piece_list_us(slider_type):
            square = Square(square_index)
            slider_moves = and64(slider_lookup(slider_type, square, board.occupancy), ~board.occupancy_us()) & allowed_squares & pin_ray_mask[square_index]
            move_list.add_moves(slider_moves, square, MoveFlag.NoFlag)


    def _update_king_moves(self, board: Board, move_list: MoveList, pieces_checking: int):

        attack_squares = self._get_enemy_attacks(board)
        king_square = board.king_square(board.side_to_move)

        valid_moves = and64((MOVEMENT_MASKS.king[king_square.value]), ~board.occupancy_us()) & ~attack_squares

        move_list.add_moves(valid_moves, king_square, MoveFlag.NoFlag)

        if board.has_short_castle_rights(board.side_to_move) and pieces_checking == 0:
            clear_squares = 96 if board.side_to_move.is_white() else 6917529027641081856

            if (clear_squares & attack_squares == 0) and (clear_squares & board.occupancy == 0):

                move_to_square = Square(6) if board.side_to_move.is_white() else Square(62)
                move_list.add_moves(move_to_square.mask(), king_square, MoveFlag.CastleShort)


        if board.has_long_castle_rights(board.side_to_move) and pieces_checking == 0:
            not_attacked_squares = 12 if board.side_to_move.is_white() else 864691128455135232
            not_occupied_squares = 14 if board.side_to_move.is_white() else 1008806316530991104

            if (not_attacked_squares & attack_squares == 0) and (not_occupied_squares & board.occupancy == 0):
                move_to_index = 2 if board.side_to_move.is_white() else 58

                move_list.add_moves(1 << move_to_index, king_square, MoveFlag.CastleLong)





    @staticmethod
    def _get_pins(board: Board, pin_ray_mask: list[int]):
        friendly_king_square = board.king_square(board.side_to_move)
        friendly_pieces = board.occupancy_us()
        enemy_pieces = board.occupancy_them()

        enemy_orthogonal = board.orthogonal_bitboard_them()
        enemy_diagonal = board.diagonal_bitboard_them()


        possible_orthogonally_pinned = MOVEMENT_MASKS.rook[friendly_king_square.value] & enemy_orthogonal
        possible_diagonally_pinned = MOVEMENT_MASKS.bishop[friendly_king_square.value] & enemy_diagonal

        possible_pinners = possible_orthogonally_pinned | possible_diagonally_pinned

        pinned_pieces_mask = 0

        while possible_pinners != 0:
            possible_pinner = lsb(possible_pinners)
            ray = IN_BETWEEN.in_between[friendly_king_square.value][possible_pinner]

            # opponents between the king and pinner
            if (ray & enemy_pieces) != 0:
                possible_pinners = pop(possible_pinners)
                continue


            friendly_pieces_between = ray & friendly_pieces

            if friendly_pieces_between.bit_count() == 1:
                pinned_pieces_mask |= friendly_pieces_between
                friendly_piece_index = lsb(friendly_pieces_between)
                pin_ray_mask[friendly_piece_index] = IN_BETWEEN.in_between[friendly_king_square.value][possible_pinner] | (1 << possible_pinner)


            possible_pinners = pop(possible_pinners)



        return pinned_pieces_mask


# Arbiter
# ----------------------------------------------------------------------------------------------------------------------

class MatchResult(Enum):
    Loss = 0
    Draw = 1
    NoResult = 2

class Arbiter:
    def arbitrate(self, board: Board, move_list: MoveList) -> MatchResult:
        if self._is_checkmate(board, move_list):
            return MatchResult.Loss

        if self._is_insufficient_material(board) or self._is_stalemate(board, move_list) or self._is_fifty_move_rule(board) or self._is_three_fold(board):
            return MatchResult.Draw

        return MatchResult.NoResult


    @staticmethod
    def _is_stalemate(board: Board, move_list: MoveList) -> bool:
        return len(move_list.moves) == 0 and not board.in_check

    @staticmethod
    def _is_checkmate(board: Board, move_list: MoveList) -> bool:
        return len(move_list.moves) == 0 and board.in_check

    @staticmethod
    def _is_fifty_move_rule(board: Board) -> bool:
        if board.half_move_clock >= 100:
            return True

        return False

    @staticmethod
    def _is_insufficient_material(board: Board) -> bool:
        if board.occupancy.bit_count() <= 3:

            if board.bitboard_combined(BasePiece.Pawn).bit_count() != 0:
                return False


            if board.bitboard_combined(BasePiece.Rook).bit_count() != 0:
                return False


            if board.bitboard_combined(BasePiece.Queen).bit_count() != 0:
                return False


            return True


        return False

    @staticmethod
    def _is_three_fold(board: Board) -> bool:
        if board.half_move_clock == 0:
            return False
        

        position_count = {board.zobrist: 1}

        past_board_states = board.past_board_states()
        if past_board_states is not None:
            for past_board_state in past_board_states[::-1]:     
                if past_board_state.zobrist in position_count:
                    position_count[past_board_state.zobrist] += 1
                else:
                    position_count[past_board_state.zobrist] = 0

                if position_count[past_board_state.zobrist] >= 3:
                    return True


                if past_board_state.half_move_clock == 0:
                    break
        return False
    

# Transposition Table
# ----------------------------------------------------------------------------------------------------------------------
NUM_TT_ENTRIES = 1 << 20
EXACT_BONUS = 3
DEPTH_MULTIPLIER = -1

class TTFlag(Enum):
    UpperBound = 0
    LowerBound = 1
    Exact = 2

TTEntry = namedtuple("BoardState", [
    "zobrist",
    "move",
    "centipawn",
    "score",
    "depth",
    "tt_flag",

], defaults=[0, Move.default(), 0, 0, 0, TTFlag.Exact] )


class TranspositionTable:
    __slots__ = ["entries", "best_move", "best_move_score"]

    def __init__(self):
        self.entries = [TTEntry() for _ in range(NUM_TT_ENTRIES) ]

    def probe(self, zobrist: int) -> TTEntry | None:
        index = zobrist & (NUM_TT_ENTRIES-1)
        entry = self.entries[index]

        if entry.zobrist == zobrist:
            return entry

        return None

    def update(self, zobrist: int, move: Move, centipawn: int, depth: int, tt_flag: TTFlag) -> None:
        score = depth * DEPTH_MULTIPLIER
        if tt_flag == TTFlag.Exact:
            score += EXACT_BONUS

        index = zobrist & (NUM_TT_ENTRIES-1)
        existing_entry = self.entries[index]

        if existing_entry.zobrist != 0 and existing_entry.score > score:
            return

        new_entry = TTEntry(zobrist, move, centipawn, score, depth, tt_flag)
        self.entries[index] = new_entry


TRANSPOSITION_TABLE = TranspositionTable()


# Thread Data
# ----------------------------------------------------------------------------------------------------------------------
class Killers:
    __slots__ = ["moves"]

    def __init__(self):
        self.moves = [[Move.default() for _ in range(2)] for _ in range(MAX_DEPTH)]

    def contains(self, depth: int, checked_move: Move) -> bool:
        if self.first_occupancy(depth) == checked_move or self.second_occupancy(depth) == checked_move:
            return True

        return False

    def first_occupancy(self, depth: int) -> Move:
        return self.moves[depth][0]

    def second_occupancy(self, depth: int) -> Move:
        return self.moves[depth][1]

    def update(self, move: Move, depth: int) -> None:
        first_occupancy = self.first_occupancy(depth)
        second_occupancy = self.second_occupancy(depth)

        if first_occupancy.is_default():
            self.moves[depth][0] = move
        elif second_occupancy.is_default():
            self.moves[depth][1] = move
        else:
            self.moves[depth][0] = move
            self.moves[depth][1] = first_occupancy

class HistoryHeuristics:
    __slots__ = ["square_data"]

    def __init__(self) -> None:
        self.square_data = [[[0 for _ in range(NUM_SQUARES)] for _ in range(NUM_SQUARES)] for _ in range(2)]

    def get_history(self, move: Move, side_to_move: Color) -> int:
        return self.square_data[side_to_move.value][move.start_square.value][move.target_square.value]

    def update_history(self, move: Move, side_to_move: Color) -> None:
        self.square_data[side_to_move.value][move.start_square.value][move.target_square.value] += 1

class SearchLimits:
    __slots__ = ["start_time", "soft_stop", "hard_stop"]

    def __init__(self, soft_stop: float, hard_stop: float) -> None:
        self.start_time = time.time()
        self.soft_stop = soft_stop
        self.hard_stop = hard_stop

    def is_soft_stop(self) -> bool:
        return time.time() > (self.start_time + self.soft_stop)

    def is_hard_stop(self) -> bool:
        return time.time() > (self.start_time + self.hard_stop)


# NNUE
# ----------------------------------------------------------------------------------------------------------------------

HIDDEN_SIZE = 64
FEATURE_SIZE = 768
CR_MIN = 0
CR_MAX = 255
QA = 255
QAB = 255*64
EVAL_SCALE = 400

# In the CMU CS Academy version this will be replaced by just putting the text value here
# The reason it's not done is to prevent my IDE from crashing
# RAW_FEATURE_WEIGHTS = open("nnue/feature_weights.txt", "r").read()
RAW_FEATURE_BIAS = 'eNoVjcEKgkAABT/Iw4hFux46PDUKCl0j/ICCXZDwkOBaX986x3kDr3QEolRia8mqU6JtsJATg+pes9wOAytxFp4TLKzOSjeH8cmbEbPYQXopTRnZg8JTwCWl9qwWqr4xmB97z0DpaEJzh4kq6q1uIjrG7fTg7VXuQ+LJpnxW8M2loOMfljQuMA=='
RAW_OUTPUT_WEIGHTS = 'eNolj8FOwzAQRD9pUiUizqGHIQu0aezGAon2WiRbasWBptiJvx5bnFaa3X0zszgckb5YAZ/orlhDJ9R3DLHfQAUkYEDnsJlU4n7EFFlzuOMYWXFosQR1pdyoo5yR9nzzkjkfWBzesTYcvZxQaY5RDNq2/P3Q3P+5ydLG3kNdELIZ9RWVUw+aXfbDAd0EzT7n08z7lqKZ/R7sZx48nzjWMLbwI43nQjkXfaau4SgC5XCJ8gqVcCr3ps55c9/1xjXgG+vMkVTsK1YBU9GDgy09rJcXdCcMlmvhJgfBpuHRP+9oRmS/3zK1zX3yPvebUDdMkwK53f4BRZJlKQ=='
RAW_OUTPUT_BIAS = 'eNpLK7OwBQADqwFS'
RAW_FEATURE_WEIGHTS = ['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']

def general_decompress(raw_data: str):
    original_base64 = bytearray(base64.b64decode(raw_data))
    if IN_CMU_EDITOR:
        original_base64[1] = 156
    decompressed_base64 = zlib.decompress(original_base64)
    base64_decoded = base64.b64decode(decompressed_base64)
    original_data = list(struct.unpack(f'<{len(base64_decoded)//2}h', base64_decoded))

    return arr.array("i", original_data)

def chunks_decompress(chunks: list[str]):
    final_data = []

    for i, chunk in enumerate(chunks):
        decompressed_chunk = general_decompress(chunk)
        final_data.extend(decompressed_chunk)

    return arr.array("i", final_data)


FEATURE_BIAS = general_decompress(RAW_FEATURE_BIAS)
OUTPUT_WEIGHTS = general_decompress(RAW_OUTPUT_WEIGHTS)
OUTPUT_BIAS = general_decompress(RAW_OUTPUT_BIAS)
FEATURE_WEIGHTS = chunks_decompress(RAW_FEATURE_WEIGHTS)

print(len(FEATURE_WEIGHTS))
class Accumulator:
    # __slots__ = ["white", "black"]

    def __init__(self) -> None:
        self.white = copy.deepcopy(FEATURE_BIAS)
        self.black = copy.deepcopy(FEATURE_BIAS)


    @staticmethod
    def nnue_index(piece: Piece, square: Square) -> tuple[int, int]:
        white_idx = NUM_SQUARES * piece.value + square.value

        reversed_color = piece.value
        if reversed_color >= 6:
            reversed_color -= 6
        else:
            reversed_color += 6

        black_idx = NUM_SQUARES * reversed_color + square.flip_vert()

        return white_idx * HIDDEN_SIZE, black_idx * HIDDEN_SIZE

    def add_piece(self, piece: Piece, square: Square) -> None:
        white_idx, black_idx = self.nnue_index(piece, square)

        for i in range(HIDDEN_SIZE):
            self.white[i] += FEATURE_WEIGHTS[i+white_idx]
            self.black[i] += FEATURE_WEIGHTS[i+black_idx]

    def remove_piece(self, piece: Piece, square: Square) -> None:
        white_idx, black_idx = self.nnue_index(piece, square)

        for i in range(HIDDEN_SIZE):
            self.white[i] -= FEATURE_WEIGHTS[i+white_idx]
            self.black[i] -= FEATURE_WEIGHTS[i+black_idx]

    def move_piece(self, piece: Piece, start_square: Square, target_square: Square) -> None:
        white_start_idx, black_start_idx = self.nnue_index(piece, start_square)
        white_target_idx, black_target_idx = self.nnue_index(piece, target_square)

        for i in range(HIDDEN_SIZE):
            self.white[i] -= FEATURE_WEIGHTS[i+white_start_idx]
            self.black[i] -= FEATURE_WEIGHTS[i+black_start_idx]

            self.white[i] += FEATURE_WEIGHTS[i+white_target_idx]
            self.black[i] += FEATURE_WEIGHTS[i+black_target_idx]

    def make_castle(self, king: Piece, rook: Piece, king_start: Square, king_target: Square, rook_start: Square, rook_target: Square) -> None:
        self.move_piece(king, king_start, king_target)
        self.move_piece(rook, rook_start, rook_target)

    def make_capture(self, piece: Piece, start: Square, target: Square, captured_piece: Piece, capture_square: Square) -> None:
        self.move_piece(piece, start, target)
        self.remove_piece(captured_piece, capture_square)

    def make_promotion(self, pawn: Piece, promotion: Piece, start: Square, target: Square) -> None:
        self.remove_piece(pawn, start)
        self.add_piece(promotion, target)


class NNUE:
    __slots__ = ["accumulator_stack", "cur_accumulator"]

    def __init__(self, board: Board) -> None:
        self.cur_accumulator = 0
        self.accumulator_stack = [Accumulator() for _ in range(MAX_DEPTH)]

        board.update_occupancy()
        occupied_squares = all_squares(board.occupancy)

        for square in occupied_squares:
            piece = board.piece_at(square)

            if piece.is_piece():
                self.accumulator_stack[self.cur_accumulator].add_piece(piece, square)


    def make_move(self, move: Move, board: Board) -> None:
        self.cur_accumulator += 1
        self.accumulator_stack[self.cur_accumulator] = copy.deepcopy(self.accumulator_stack[self.cur_accumulator-1])
        current_accumulator = self.accumulator_stack[self.cur_accumulator]

        move_flag =  move.move_flag
        start_square = move.start_square
        target_square = move.target_square

        piece = board.piece_at(start_square)
        capture= board.piece_at(target_square)


        if move_flag == MoveFlag.NoFlag:
            match capture.is_piece():
                case True: current_accumulator.make_capture(piece, start_square, target_square, capture, target_square)
                case False: current_accumulator.move_piece(piece, start_square, target_square)


        elif move_flag == MoveFlag.DoubleJump:
            current_accumulator.move_piece(piece, start_square, target_square)


        elif move_flag == MoveFlag.CastleShort:
            match board.side_to_move:
                case Color.White: current_accumulator.make_castle(Piece.WhiteKing, Piece.WhiteRook, Square.E1, Square.G1, Square.H1, Square.F1)
                case Color.Black: current_accumulator.make_castle(Piece.BlackKing, Piece.BlackRook, Square.E8, Square.G8, Square.H8, Square.F8)



        elif move_flag == MoveFlag.CastleLong:
            match board.side_to_move:
                case Color.White: current_accumulator.make_castle(Piece.WhiteKing, Piece.WhiteRook, Square.E1, Square.C1, Square.A1, Square.D1)
                case Color.Black: current_accumulator.make_castle(Piece.BlackKing, Piece.BlackRook, Square.E8, Square.C8, Square.A8, Square.D8)



        elif move_flag.is_promotion():
            promotion_piece = move_flag.promotion_piece(board.side_to_move)
            if capture.is_piece():
                current_accumulator.remove_piece(capture, target_square)

            current_accumulator.make_promotion(piece, promotion_piece, start_square, target_square)


        elif move_flag == MoveFlag.EnPassant:
            enemy_pawn_square = Square.A1

            match board.side_to_move:
                case Color.White: enemy_pawn_square = Square(board.en_passant_file.value + 32)
                case Color.Black: enemy_pawn_square = Square(board.en_passant_file.value + 24)


            enemy_pawn = board.piece_at(enemy_pawn_square)

            current_accumulator.make_capture(piece, start_square, target_square, enemy_pawn, enemy_pawn_square)

    def undo_move(self):
        self.cur_accumulator -= 1

    def evaluate(self, side_to_move: Color) -> int:

        screlu = lambda result: min(max(CR_MIN, result), CR_MAX) ** 2

        white_accumulator = self.accumulator_stack[self.cur_accumulator].white
        black_accumulator = self.accumulator_stack[self.cur_accumulator].black

        us = white_accumulator if side_to_move == Color.White else black_accumulator
        them = black_accumulator if side_to_move == Color.White else white_accumulator

        out = 0
        for value, weight in zip(us, OUTPUT_WEIGHTS[:HIDDEN_SIZE]):
            out += screlu(value) * weight

        for value, weight in zip(them, OUTPUT_WEIGHTS[HIDDEN_SIZE:]):
            out += screlu(value) * weight

        result =  int((int(out / QA) + OUTPUT_BIAS[0]) * EVAL_SCALE / QAB)

        return result





# Search
# ----------------------------------------------------------------------------------------------------------------------

def order_moves(board: Board, move_list: MoveList, prev_best_move: TTEntry, history_heuristics: HistoryHeuristics, killers: Killers, ply_searched: int):

    move_values = [0 for _ in range(len(move_list.moves))]
    for i, cur_move in enumerate(move_list.moves):
        flag = cur_move.move_flag

        if prev_best_move is not None:
            if prev_best_move.move == cur_move:
                move_values[i] = INFINITY
                continue

        if killers.contains(ply_searched, cur_move):
            move_values[i] += 5000

        # see

        if flag.is_promotion():
            move_values[i] += PIECE_VALUES[flag.promotion_piece(Color.White).value] * 10

        if flag.is_castles():
            move_values[i] += 1000

        move_values[i] += history_heuristics.get_history(cur_move, board.side_to_move)


def move_causes_check(move: Move, board: Board) -> bool:
    piece = board.piece_at(move.start_square)
    square = move.target_square
    enemy_king = board.king_square(~board.side_to_move)
    enemy_king_mask = enemy_king.mask()

    if piece.is_pawn():
        if MOVEMENT_MASKS.pawn_attacks(board.side_to_move, square) & enemy_king_mask != 0:
            return True
    elif piece == Piece.WhiteKnight or piece == Piece.BlackKnight:
        if MOVEMENT_MASKS.knight[square.value] & enemy_king_mask != 0:
            return True
    elif piece == Piece.WhiteRook or piece == Piece.BlackRook:
        if ROOK_LOOKUP.get(square, board.occupancy) & enemy_king_mask != 0:
            return True
    elif piece == Piece.WhiteBishop or piece == Piece.BlackBishop:
        if BISHOP_LOOKUP.get(square, board.occupancy) & enemy_king_mask != 0:
            return True
    elif piece == Piece.WhiteQueen or piece == Piece.BlackQueen:
        if slider_lookup(BasePiece.Queen, square, board.occupancy)  & enemy_king_mask != 0:
            return True

    return False

def quiescence_search(board: Board,
           ply_searched: int,
           alpha: int,
           beta: int,
           nnue: NNUE,
           search_limits: SearchLimits) -> int:

    if search_limits.is_hard_stop():
        return 0
    #
    tt_entry = TRANSPOSITION_TABLE.probe(board.zobrist)
    if tt_entry is not None:
            if tt_entry.tt_flag == TTFlag.Exact: return tt_entry.centipawn

            elif tt_entry.tt_flag == TTFlag.UpperBound:
                if tt_entry.centipawn <= alpha: return tt_entry.centipawn
            elif tt_entry.tt_flag == TTFlag.LowerBound:
                if tt_entry.centipawn >= beta: return tt_entry.centipawn

    centipawn = nnue.evaluate(board.side_to_move)
    if centipawn >= beta:
        return beta

    if centipawn > alpha:
        alpha = centipawn

    move_list = MoveGenerator().generator(board)

    match_result = Arbiter().arbitrate(board, move_list)
    match match_result:
        case MatchResult.Draw:
            return 0
        case MatchResult.Loss:
            return -INFINITY + ply_searched
        case MatchResult.NoResult:
            pass


    node_type = TTFlag.UpperBound
    best_move = move_list.moves[0]
    best_move_score = -INFINITY

    for move in move_list.moves:
        is_capture = board.piece_at(move.target_square).is_piece() or move.move_flag.is_en_passant_capture()
        if not move.move_flag.is_promotion() and not is_capture and not move_causes_check(move, board):
            continue
        # if not is_capture:
        #     continue

        nnue.make_move(move, board)
        board.make_move(move)

        centipawn = -quiescence_search(board, ply_searched+1, -beta, -alpha, nnue, search_limits)

        if search_limits.is_hard_stop():
            return 0

        board.undo_move()
        nnue.undo_move()

        if centipawn >= beta:
            TRANSPOSITION_TABLE.update(board.zobrist, move, alpha, 0, TTFlag.LowerBound)
            return beta

        if centipawn > alpha:
            best_move = move
            node_type = TTFlag.Exact
            alpha = centipawn

        if centipawn > best_move_score:
            best_move_score = centipawn
            best_move = move

    TRANSPOSITION_TABLE.update(board.zobrist, best_move, alpha, 0, node_type)

    return alpha


def search(board: Board,
           ply_searched: int,
           depth: int,
           alpha: int,
           beta: int,
           killers: Killers,
           history_heuristics: HistoryHeuristics,
           nnue: NNUE,
           search_limits: SearchLimits) -> int:

    if search_limits.is_hard_stop():
        return 0

    # beautiful nesting
    tt_entry = TRANSPOSITION_TABLE.probe(board.zobrist)
    if tt_entry is not None:
        if tt_entry.depth >= depth:
            if tt_entry.tt_flag == TTFlag.Exact:
                if ply_searched == 0:
                    TRANSPOSITION_TABLE.best_move = tt_entry.move
                    TRANSPOSITION_TABLE.best_move_score = tt_entry.centipawn

                return tt_entry.centipawn
            elif tt_entry.tt_flag == TTFlag.UpperBound:
                if tt_entry.centipawn <= alpha:
                    return tt_entry.centipawn
            elif tt_entry.tt_flag == TTFlag.LowerBound:
                if tt_entry.centipawn >= beta:
                    return tt_entry.centipawn

    move_list = MoveGenerator().generator(board)

    match_result = Arbiter().arbitrate(board, move_list)
    match match_result:
        case MatchResult.Draw: return 0
        case MatchResult.Loss: return -INFINITY + ply_searched
        case MatchResult.NoResult: pass

    if board.in_check:
        depth += 1

    if depth <= 0:
        # return nnue.evaluate(board.side_to_move)
        return quiescence_search(board, ply_searched+1, alpha, beta, nnue, search_limits)

    # if tt_entry is not None:
    #     static_eval = tt_entry.centipawn
    # else:
    #     static_eval = nnue.evaluate(board.side_to_move)
    #
    # if static_eval >= (beta + 80 * depth):
    #     return beta

    # if depth > 4 and tt_entry is None:
    #     depth -= 1

    order_moves(board, move_list, tt_entry, history_heuristics, killers, ply_searched)

    node_type = TTFlag.UpperBound
    best_eval = -INFINITY
    best_move = move_list.moves[0]

    for (i, cur_move) in enumerate(move_list.moves):
        nnue.make_move(cur_move, board)
        board.make_move(cur_move)

        # centipawn = -search(board, ply_searched + 1, depth - 1, -beta, -alpha, killers, history_heuristics, tt, nnue, search_limits)
        # centipawn = 0
        if i >= 2 and depth >= 2:
            centipawn = -search(board, ply_searched+1, depth-2, -alpha - 1, -alpha, killers, history_heuristics, nnue, search_limits)
            if search_limits.is_hard_stop():
                return 0

            if centipawn > alpha:
                centipawn = -search(board, ply_searched + 1, depth - 1, -beta, -alpha, killers, history_heuristics, nnue, search_limits)
        else:
            centipawn = -search(board, ply_searched + 1, depth - 1, -beta, -alpha, killers, history_heuristics, nnue, search_limits)


        if search_limits.is_hard_stop():
            return 0

        board.undo_move()
        nnue.undo_move()

        # if ply_searched == 0:
        #     print(cur_move, centipawn)

        if centipawn >= beta:
            TRANSPOSITION_TABLE.update(board.zobrist, cur_move, beta, depth, TTFlag.LowerBound)
            killers.update(cur_move, ply_searched)
            history_heuristics.update_history(cur_move, board.side_to_move)
            return beta

        if centipawn > alpha:
            alpha = centipawn
            node_type = TTFlag.Exact
            best_move = cur_move

        if centipawn > best_eval:
            best_eval = centipawn
            best_move = cur_move

    TRANSPOSITION_TABLE.update(board.zobrist, best_move, alpha, depth, node_type)

    if ply_searched == 0:
        TRANSPOSITION_TABLE.best_move = best_move
        TRANSPOSITION_TABLE.best_move_score = alpha

    return alpha


def iterative_deepening(board: Board, time_remaining_sec: int):
    nnue = NNUE(board)
    killers = Killers()
    history_heuristics = HistoryHeuristics()

    hard_limit = time_remaining_sec / 20
    soft_limit = hard_limit * .6

    search_limits = SearchLimits(soft_limit, hard_limit)

    start_time = time.time()
    for cur_depth in range(1, 6):
        print(cur_depth, time.time() - start_time)
        search(copy.deepcopy(board), 0, cur_depth, -INFINITY, INFINITY, killers, history_heuristics, nnue, search_limits)
        if search_limits.is_soft_stop() or search_limits.is_hard_stop():
            break


    return TRANSPOSITION_TABLE.best_move
    # while True:
    #     tt_entry = TRANSPOSITION_TABLE.probe(board.zobrist)
    #     if tt_entry is not None:
    #         best_move = tt_entry.move
    #         print(best_move)
    #         board.make_move(best_move)
    #     else:
    #         break




def run_perft(fen: str) -> None:
    def perft(board: Board, depth: int, ply_searched: int, nodes: int) -> int:

        move_list = MoveGenerator().generator(board).moves

        if depth == 1:
            return len(move_list)


        for move in move_list:
            board.make_move(move)

            cur_nodes = perft(board, depth-1, ply_searched+1, 0)
            if ply_searched == 0:
                print(f"{move}: {cur_nodes}")
            nodes += cur_nodes

            board.undo_move()

        return nodes

    board = Board(fen)

    start_time = time.time()
    num_nodes = perft(board, 3, 0, 0)
    print(f"Time elapsed: {time.time() - start_time}")
    print(f"Nodes: {num_nodes}")





# GUI Control
# ----------------------------------------------------------------------------------------------------------------------
WINDOW_SIZE = 400
SQUARE_SIZE = 40
PRIMARY_SQUARE_COLOR = rgb(115, 149, 82)
SECONDARY_SQUARE_COLOR = rgb(235, 236, 208)
ACCENT_COLOR = rgb(0, 171, 235)

TIME_CONTROL_MENU_SIZE = (350, 220)
TIME_CONTROL_MENU_COLOR = rgb(38, 37, 34)
TIME_CONTROL_ICON_COLOR = rgb(60, 59, 57)
TIME_CONTROL_TEXT_COLOR = rgb(226, 226, 225)
TIME_CONTROL_MENU_PADDING = 8
TIME_CONTROL_ICON_NAMES = ["BULLET", "BLITZ", "BLITZ", "RAPID"]
TIME_CONTROL_TIMES = [1, 3, 5, 10]

BACKGROUND_COLOR = rgb(48, 46, 43)
PIECE_IMG_LOOKUP_LOCAL = ["cmu://1067374/42057363/whitepawn.png", "cmu://1067374/42057371/whiteknight.png", "cmu://1067374/42057374/whitebishop.png", "cmu://1067374/42057378/whiterook.png", "cmu://1067374/42057383/whitequeen.png", "cmu://1067374/42057412/whiteking.png", "cmu://1067374/42057424/blackpawn.png", "cmu://1067374/42057427/blackknight.png", "cmu://1067374/42057447/black-bishop.png", "cmu://1067374/42057452/blackrook.png", "cmu://1067374/42057456/blackqueen.png", "cmu://1067374/42057459/blackking.png"]
CENTER_OFFSET = (WINDOW_SIZE - SQUARE_SIZE * NUM_FILES) // 2



TIMER_MARGIN = 8
TIMER_SIZE = (80, CENTER_OFFSET-TIMER_MARGIN*2)
WHITE_TIMER_POSITION = (400-TIMER_SIZE[0]/2-CENTER_OFFSET, 400 - CENTER_OFFSET/2)
BLACK_TIMER_POSITION = (400-TIMER_SIZE[0]/2-CENTER_OFFSET, CENTER_OFFSET/2)
WHITE_TIMER_BACKGROUND_POSITION = (400-TIMER_SIZE[0]-CENTER_OFFSET, 400 - CENTER_OFFSET+TIMER_MARGIN)
BLACK_TIMER_BACKGROUND_POSITION = (400-TIMER_SIZE[0]-CENTER_OFFSET, TIMER_MARGIN)

class PlayerTimer:
    def __init__(self, time_control_minutes: int) -> None:
        self.white_time_sec = time_control_minutes*60
        self.black_time_sec = time_control_minutes*60
        self.is_running = True

        self.cur_player = Color.White

        Rect(BLACK_TIMER_BACKGROUND_POSITION[0], BLACK_TIMER_BACKGROUND_POSITION[1], TIMER_SIZE[0], TIMER_SIZE[1], fill=TIME_CONTROL_MENU_COLOR)
        Rect(WHITE_TIMER_BACKGROUND_POSITION[0], WHITE_TIMER_BACKGROUND_POSITION[1], TIMER_SIZE[0], TIMER_SIZE[1], fill="white")

        self.black_timer_label = Label(f"{time_control_minutes}:00", BLACK_TIMER_POSITION[0], BLACK_TIMER_POSITION[1], size=20, fill='white', bold=True)
        self.white_timer_label = Label(f"{time_control_minutes}:00", WHITE_TIMER_POSITION[0], WHITE_TIMER_POSITION[1], size=20, fill=TIME_CONTROL_MENU_COLOR, bold=True)

        # threading.Thread(target=self._ticker).start()

    def switch_side_to_move(self) -> None:
        self.cur_player = ~self.cur_player

    def side_to_move_time_left(self) -> int:
        if self.cur_player == Color.White:
            return self.white_time_sec

        return self.black_time_sec

    def stop_timer(self) -> None:
        self.is_running = False

    def _ticker(self) -> None:
        while self.white_time_sec > 0 and self.black_time_sec > 0 and self.is_running:
            if self.cur_player == Color.White:
                self.white_time_sec -= 1

                minutes_left = self.white_time_sec // 60
                seconds_left = str(self.white_time_sec % 60).rjust(2, "0")

                self.white_timer_label.value = f"{minutes_left}:{seconds_left}"

            if self.cur_player == Color.Black:
                self.black_time_sec -= 1

                minutes_left = self.black_time_sec // 60
                seconds_left = str(self.black_time_sec % 60).rjust(2, "0")

                self.black_timer_label.value = f"{minutes_left}:{seconds_left}"


            sleep(1)



    # def _draw



class GUI:

    def __init__(self):
        self.player_timers = None
        self.pieces = [Image(PIECE_IMG_LOOKUP_LOCAL[0], 0, 0, visible=False) for _ in range(NUM_SQUARES)]
        self.squares = [Rect(0, 0, SQUARE_SIZE, SQUARE_SIZE, visible=False) for _ in range(NUM_SQUARES)]
        self.accent_squares = [Rect(0, 0, SQUARE_SIZE, SQUARE_SIZE, visible=False, opacity=50, fill=ACCENT_COLOR) for _ in range(NUM_SQUARES)]
        self.is_game_over = False

        self.is_holding_piece = False
        self.piece_held = self.pieces[0]
        self.original_held_square = Square.A1
        self.board = Board(STARTING_FEN)

        self.menu_open = True
        self.time_control_minutes = 0

        Rect(0, 0, WINDOW_SIZE, WINDOW_SIZE, fill=BACKGROUND_COLOR)
        self._draw_board()
        self._draw_time_control_selector()

        # threading.Thread(target=self._handle_user_input()).start()

    def select_time_control(self, time_control: int):
        self.time_control_minutes = time_control
        for value in self.time_control_elements.values():
            if type(value) == list:
                for item in value:
                    item.visible = False
            else:
                value.visible = False

        self.menu_open = False
        self.player_timers = PlayerTimer(self.time_control_minutes)

    def _draw_time_control_selector(self) -> None:

        background_blur = Rect(0, 0, WINDOW_SIZE, WINDOW_SIZE, fill=BACKGROUND_COLOR, opacity=80)

        background_x = (400 - TIME_CONTROL_MENU_SIZE[0])/2
        background_y =  (400 - TIME_CONTROL_MENU_SIZE[1])/2
        background_fill = Rect(background_x, background_y, TIME_CONTROL_MENU_SIZE[0], TIME_CONTROL_MENU_SIZE[1], fill=TIME_CONTROL_MENU_COLOR)

        menu_label = Label("Time Control Selector", 200, background_y-TIME_CONTROL_MENU_PADDING*3, fill=TIME_CONTROL_TEXT_COLOR, size=20, bold=True)

        icon_size = ((TIME_CONTROL_MENU_SIZE[0] - TIME_CONTROL_MENU_PADDING*3)/2, (TIME_CONTROL_MENU_SIZE[1] - TIME_CONTROL_MENU_PADDING*3)/2)
        icon_pos = (background_x+TIME_CONTROL_MENU_PADDING, background_y+TIME_CONTROL_MENU_PADDING)
        right_x_offset = TIME_CONTROL_MENU_PADDING+icon_size[0]
        down_y_offset = TIME_CONTROL_MENU_PADDING+icon_size[1]

        icon1 = Rect(icon_pos[0], icon_pos[1], icon_size[0], icon_size[1], fill=TIME_CONTROL_ICON_COLOR)
        icon2 = Rect(icon_pos[0]+right_x_offset, icon_pos[1], icon_size[0], icon_size[1], fill=TIME_CONTROL_ICON_COLOR)
        icon3 = Rect(icon_pos[0], icon_pos[1]+down_y_offset, icon_size[0], icon_size[1], fill=TIME_CONTROL_ICON_COLOR)
        icon4 = Rect(icon_pos[0]+right_x_offset, icon_pos[1]+down_y_offset, icon_size[0], icon_size[1], fill=TIME_CONTROL_ICON_COLOR)

        icon_list = [icon1, icon2, icon3, icon4]
        control_type_list = []
        match_length_list = []

        for (i, (control_type, length)) in enumerate(zip(TIME_CONTROL_ICON_NAMES, TIME_CONTROL_TIMES)):
            icon_background = icon_list[i]

            control_type = Label(f"{control_type}", icon_background.centerX, icon_background.centerY-TIME_CONTROL_MENU_PADDING*2, size=16, bold=True, fill=TIME_CONTROL_TEXT_COLOR)
            match_length = Label(f"{length} Minute", icon_background.centerX, icon_background.centerY+TIME_CONTROL_MENU_PADDING*2, size=14, bold=True, fill=TIME_CONTROL_TEXT_COLOR)

            control_type_list.append(control_type)
            match_length_list.append(match_length)

        self.time_control_elements = {
            "background_blur": background_blur,
            "background_fill": background_fill,
            "menu_label": menu_label,
            "icon_list": icon_list,
            "control_type_list": control_type_list,
            "match_length_list": match_length_list,
        }


    def update_from_board(self) -> None:
        for square_index in range(NUM_SQUARES):
            square = Square(square_index)
            piece_type = self.board.piece_at(square)

            self.pieces[square.value].visible = False

            if piece_type.is_piece():
                x_pos = square.file().value * SQUARE_SIZE + CENTER_OFFSET
                y_pos = (7-square.rank().value) * SQUARE_SIZE + CENTER_OFFSET
                piece = Image(PIECE_IMG_LOOKUP_LOCAL[piece_type.value], x_pos, y_pos, width=SQUARE_SIZE,height=SQUARE_SIZE)
                piece.visible = True
                self.pieces[square.value] = piece


    def _draw_board(self) -> None:
        for file in range(NUM_FILES):
            for rank in range(NUM_FILES):
                x_pos = file*SQUARE_SIZE+CENTER_OFFSET
                y_pos = rank*SQUARE_SIZE+CENTER_OFFSET

                square_color = PRIMARY_SQUARE_COLOR if ((file+rank) % 2) != 0 else SECONDARY_SQUARE_COLOR
                accent_color = PRIMARY_SQUARE_COLOR if ((file+rank) % 2) == 0 else SECONDARY_SQUARE_COLOR

                square = Square.from_file_rank(File(file), Rank(7-rank))

                rect = self.squares[square.value]
                rect.centerX = x_pos+SQUARE_SIZE//2
                rect.centerY = y_pos+SQUARE_SIZE//2
                rect.fill = square_color
                rect.visible = True
                rect.toFront()

                accent_square = self.accent_squares[square.value]
                accent_square.toFront()
                accent_square.centerX = x_pos+SQUARE_SIZE//2
                accent_square.centerY = y_pos+SQUARE_SIZE//2

                # Rect(x_pos, y_pos, SQUARE_SIZE, SQUARE_SIZE, fill=square_color)

                if rank == 7:
                    text_offset = (SQUARE_SIZE-(SQUARE_SIZE//6))
                    Label(File(file).__str__(), x_pos+text_offset, y_pos+text_offset, size=11, fill=accent_color)

                if file == 0:
                    text_offset = (SQUARE_SIZE//6)
                    Label(Rank(7-rank).__str__(), x_pos+(text_offset//1.5), y_pos+text_offset, size=11, fill=accent_color)


                piece_on_square = self.board.piece_at(square)
                if piece_on_square.is_piece():
                    piece = Image(PIECE_IMG_LOOKUP_LOCAL[piece_on_square.value], x_pos, y_pos, width=SQUARE_SIZE, height=SQUARE_SIZE)
                    piece.toFront()
                    self.pieces[square.value] = piece

    def _check_and_draw_result_menu(self) -> None:

        valid_moves = MoveGenerator().generator(self.board)
        match_result = Arbiter().arbitrate(self.board, valid_moves)

        if match_result == MatchResult.Draw:
            result_text = "Game has been drawn!"
        elif match_result == MatchResult.Loss:
            if self.board.side_to_move == Color.White:
                result_text = "Black has won by checkmate!"
            else:
                result_text = "White has won by checkmate!"
        elif self.player_timers.white_time_sec == 0:
            result_text = "Black has won on time!"
        elif self.player_timers.black_time_sec == 0:
            result_text = "White has won on time!"
        else:
            return

        self.player_timers.stop_timer()
        background_x = (400 - TIME_CONTROL_MENU_SIZE[0])/2
        background_y =  (400 - TIME_CONTROL_MENU_SIZE[1])/2
        Rect(0, 0, WINDOW_SIZE, WINDOW_SIZE, fill=BACKGROUND_COLOR, opacity=80)
        Rect(background_x, background_y, TIME_CONTROL_MENU_SIZE[0], TIME_CONTROL_MENU_SIZE[1], fill=TIME_CONTROL_MENU_COLOR)

        Label(result_text, 200, background_y+TIME_CONTROL_MENU_SIZE[1]/2, fill=TIME_CONTROL_TEXT_COLOR, size=20, bold=True)


    def update_from_engine(self) -> None:
        self.player_timers.switch_side_to_move()
        best_move = iterative_deepening(self.board, self.player_timers.side_to_move_time_left())
        self.board.make_move(best_move)
        self.update_from_board()
        self.player_timers.switch_side_to_move()

        self._check_and_draw_result_menu()


    def update_board(self, start: Square, target: Square) -> None:
        flag = MoveFlag.NoFlag

        piece_type = self.board.piece_at(start)
        piece_color = self.board.side_to_move

        if piece_type.is_pawn():
            if target.rank().is_pawn_promotion(piece_color):
                flag = MoveFlag.PromoteQueen
            elif target.rank().is_pawn_start(piece_color):
                flag = MoveFlag.DoubleJump
            elif target.file() != start.file() and not self.board.piece_at(target).is_piece():
                flag = MoveFlag.EnPassant

        if piece_type.is_king():
            if (start == Square.E1 and target == Square.G1) or (start == Square.E8 and target == Square.G8):
                flag = MoveFlag.CastleShort

            if (start == Square.E1 and target == Square.C1) or (start == Square.E8 and target == Square.C8):
                flag = MoveFlag.CastleLong

        self._check_and_draw_result_menu()

        if not self.is_game_over:
            self.board.make_move(Move(start, target, flag))
            self.update_from_engine()
            # threading.Thread(target=self.update_from_engine).start()




    def highlight_squares(self, square: Square):
        if self.player_timers.cur_player == Color.Black:
            return

        moves = MoveGenerator().generator(self.board).moves
        for move in moves:
            if move.start_square == square:
                accent_square = self.accent_squares[move.target_square.value]
                accent_square.visible = True

        self.accent_squares[square.value].visible = True


    def unhighlight_squares(self):
        for square in self.accent_squares:
            square.visible = False







GRAPHICS_INTERFACE = GUI()

def gui_piece_at(mouse_x, mouse_y) -> tuple[Square, Image] | None:
    if not (CENTER_OFFSET < mouse_x < (WINDOW_SIZE - CENTER_OFFSET)) or not (
            CENTER_OFFSET < mouse_y < (WINDOW_SIZE - CENTER_OFFSET)):
        return None

    file = File((mouse_x - CENTER_OFFSET) // SQUARE_SIZE)
    rank = Rank(7 - ((mouse_y - CENTER_OFFSET) // SQUARE_SIZE))
    square_clicked = Square.from_file_rank(file, rank)

    img = GRAPHICS_INTERFACE.pieces[square_clicked.value]

    return square_clicked, img


def onMousePress(mouse_x, mouse_y):

    def manage_board():
        # returns early if not on the board
        result = gui_piece_at(mouse_x, mouse_y)

        if GRAPHICS_INTERFACE.is_holding_piece:
            return

        if result is not None:
            square, img = result

            GRAPHICS_INTERFACE.original_held_square = square

            img.toFront()
            GRAPHICS_INTERFACE.piece_held = img
            GRAPHICS_INTERFACE.is_holding_piece = True

            img.centerX = mouse_x
            img.centerY = mouse_y

            GRAPHICS_INTERFACE.highlight_squares(square)

    def manage_time_control():
        icon_backgrounds = GRAPHICS_INTERFACE.time_control_elements["icon_list"]

        for i, icon_background in enumerate(icon_backgrounds):
            if icon_background.hits(mouse_x, mouse_y):
                GRAPHICS_INTERFACE.select_time_control(TIME_CONTROL_TIMES[i])



    if GRAPHICS_INTERFACE.menu_open:
        manage_time_control()
    elif not GRAPHICS_INTERFACE.is_game_over:
        manage_board()



def onMouseDrag(mouse_x, mouse_y):
    if not GRAPHICS_INTERFACE.is_holding_piece:
        return

    GRAPHICS_INTERFACE.piece_held.centerX = mouse_x
    GRAPHICS_INTERFACE.piece_held.centerY = mouse_y


def onMouseRelease(mouse_x, mouse_y):

    if not GRAPHICS_INTERFACE.is_holding_piece:
        return

    result = gui_piece_at(mouse_x, mouse_y)

    if result is not None:
        release_square, piece_at_release = result

        if GRAPHICS_INTERFACE.accent_squares[release_square.value].visible:

            if release_square.value != GRAPHICS_INTERFACE.original_held_square.value:
                GRAPHICS_INTERFACE.pieces[release_square.value].visible = False
                GRAPHICS_INTERFACE.pieces[release_square.value] = GRAPHICS_INTERFACE.piece_held

                GRAPHICS_INTERFACE.pieces[GRAPHICS_INTERFACE.original_held_square.value] = Image(PIECE_IMG_LOOKUP_LOCAL[0], 0, 0, visible=False)

                GRAPHICS_INTERFACE.update_board(GRAPHICS_INTERFACE.original_held_square, release_square)
                GRAPHICS_INTERFACE.update_from_board()

            GRAPHICS_INTERFACE.piece_held.centerX = release_square.file().value * SQUARE_SIZE + CENTER_OFFSET + SQUARE_SIZE // 2
            GRAPHICS_INTERFACE.piece_held.centerY = (7 - release_square.rank().value) * SQUARE_SIZE + CENTER_OFFSET + SQUARE_SIZE // 2
        else:
            GRAPHICS_INTERFACE.piece_held.centerX = GRAPHICS_INTERFACE.original_held_square.file().value * SQUARE_SIZE + CENTER_OFFSET + SQUARE_SIZE // 2
            GRAPHICS_INTERFACE.piece_held.centerY = (7 - GRAPHICS_INTERFACE.original_held_square.rank().value) * SQUARE_SIZE + CENTER_OFFSET + SQUARE_SIZE // 2

    GRAPHICS_INTERFACE.is_holding_piece = False
    GRAPHICS_INTERFACE.unhighlight_squares()
    GRAPHICS_INTERFACE.piece_held.centerX = GRAPHICS_INTERFACE.original_held_square.file().value * SQUARE_SIZE + CENTER_OFFSET + SQUARE_SIZE // 2
    GRAPHICS_INTERFACE.piece_held.centerY = (7 - GRAPHICS_INTERFACE.original_held_square.rank().value) * SQUARE_SIZE + CENTER_OFFSET + SQUARE_SIZE // 2


def onMouseMove(mouse_x, mouse_y):
    if GRAPHICS_INTERFACE.menu_open:
        icon_backgrounds = GRAPHICS_INTERFACE.time_control_elements["icon_list"]

        for icon_background in icon_backgrounds:
            if icon_background.hits(mouse_x, mouse_y):
                icon_background.opacity = 50
            else:
                icon_background.opacity = 100

run_perft(STARTING_FEN)

if __name__ == '__main__':
    # iterative_deepening()
    # threading.Thread(target=run_perft, args=(STARTING_FEN,)).start()
    pass
    # print("main")

    # print(tt.best_move)
    # print(tt.best_move_score)





