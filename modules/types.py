from enum import Enum

class QueryType(Enum):
    DISCOURSE = "discourse"   # Vergleich, Debatte, Entwicklung (v47 Standard)
    EXEGESIS = "exegesis"     # Erklärung, Definition, Was-wäre-wenn (v48 Neu)