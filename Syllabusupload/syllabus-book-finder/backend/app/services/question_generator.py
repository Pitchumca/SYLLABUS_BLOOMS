import os
import re
import random
import json
from typing import List, Dict, Any, Optional, Tuple

from app.services.alignment_engine import parse_syllabus_topics
from app.services.grammar_validator import clean_academic_language, validate_question_grammar
from app.services.semantic_validator import (
    evaluate_semantic_quality,
    evaluate_or_pair_equivalence,
    BLOOM_ACTION_VERBS
)

# Bloom Compatibility Matrix for Module D Multi-Question Type Validation
BLOOM_COMPATIBILITY_MATRIX = {
    "L1": ["mcq", "fill_in_blank", "true_false", "short_answer", "matching", "concept_definition", "sequencing"],
    "L2": ["mcq", "multiple_select", "short_answer", "descriptive", "code_snippet_analysis", "matching", "give_reasons", "differentiate"],
    "L3": ["programming", "numerical_problem", "debugging", "sql_query", "assertion_reason", "derivation", "multiple_select"],
    "L4": ["programming", "debugging", "code_snippet_analysis", "case_study", "comparative_analysis", "sql_query", "proof", "architecture_diagram", "derivation", "differentiate"],
    "L5": ["case_study", "comparative_analysis", "open_ended_research", "assertion_reason", "design_application", "proof"],
    "L6": ["design_application", "programming", "architecture_diagram", "open_ended_research", "case_study"]
}

def validate_type_bloom_compatibility(q_types: List[str], bloom_level: str) -> Tuple[bool, List[str]]:
    """
    Validates question types against the section's Bloom level.
    Returns (is_compatible, list_of_warning_messages).
    """
    if not bloom_level:
        return True, []

    bloom_key = bloom_level.split(" ")[0].strip().upper()
    if bloom_key not in BLOOM_COMPATIBILITY_MATRIX:
        return True, []

    compatible = BLOOM_COMPATIBILITY_MATRIX[bloom_key]
    warnings = []

    for q_type in q_types:
        parts = [p.strip() for p in re.split(r'[\+,]', str(q_type))]
        for p in parts:
            if p and p not in compatible:
                rec_blooms = [lvl for lvl, types in BLOOM_COMPATIBILITY_MATRIX.items() if p in types]
                rec_str = ", ".join(rec_blooms) if rec_blooms else "other Bloom levels"
                warnings.append(
                    f"Question type '{p.replace('_', ' ').title()}' is typically aligned with {rec_str}. "
                    f"Your section specifies {bloom_level}. We recommend adjusting the Bloom level or selecting an aligned question type."
                )

    return (len(warnings) == 0), warnings

def normalize_question_types(question_type: Any) -> List[str]:
    """Normalize question_type whether string, delimited string, or list into a list of type keys."""
    if isinstance(question_type, list):
        res = []
        for item in question_type:
            if isinstance(item, dict):
                t = item.get("question_type") or item.get("id") or ""
            else:
                t = str(item)
            for sub in re.split(r'[\+,]', t):
                sub = sub.strip()
                if sub:
                    res.append(sub)
        return res or ["short_answer"]
    elif isinstance(question_type, str):
        parts = [p.strip() for p in re.split(r'[\+,]', question_type) if p.strip()]
        return parts or ["short_answer"]
    return ["short_answer"]

# Comprehensive R Programming Question Repository Grounded in Syllabus Units 1 to 5
# Provides authentic, discipline-specific questions across all 17 supported types and Bloom levels L1-L6
R_PROGRAMMING_QUESTION_BANK = {
    "1": {
        "unit_title": "Introduction",
        "co": "CO1",
        "mcq": [
            {
                "topic": "Vectors",
                "stem": "In R, what is the result of adding two numeric vectors of unequal lengths, `x <- c(1, 2)` and `y <- c(10, 20, 30, 40)`?",
                "options": [
                    {"label": "A", "text": "An error is raised due to incompatible vector dimensions.", "is_correct": False},
                    {"label": "B", "text": "`c(11, 22, 31, 42)` because the shorter vector is recycled.", "is_correct": True},
                    {"label": "C", "text": "`c(11, 22, 10, 20)` because NA values are appended to the shorter vector.", "is_correct": False},
                    {"label": "D", "text": "`c(11, 22)` as only elements up to the length of the shorter vector are added.", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "R utilizes the recycling rule when performing element-wise vector arithmetic. Since length(y) is an exact multiple of length(x), vector x is repeated to become c(1, 2, 1, 2), yielding c(11, 22, 31, 42) with no warning.",
                "model_answer": "Correct Option: B.\n\nExplanation: R utilizes the recycling rule when performing element-wise vector arithmetic. Since length(y) is an exact multiple of length(x), vector x is repeated to become c(1, 2, 1, 2), yielding c(11, 22, 31, 42) with no warning.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. R does not throw an error; it automatically applies the recycling rule.",
                    "B": "Correct. The elements of x are recycled to match the length of y.",
                    "C": "Incorrect. R does not pad with NA values when lengths are integer multiples.",
                    "D": "Incorrect. R extends operations across the full length of the longer vector."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            },
            {
                "topic": "NA and NULL values",
                "stem": "Which of the following statements correctly distinguishes between `NA` and `NULL` in R?",
                "options": [
                    {"label": "A", "text": "`NA` represents missing or unavailable data with a specific mode, whereas `NULL` represents the empty object of length zero.", "is_correct": True},
                    {"label": "B", "text": "`NA` has length zero, while `NULL` retains a length of one with logical mode.", "is_correct": False},
                    {"label": "C", "text": "Both `NA` and `NULL` can be stored as individual elements inside a standard atomic vector.", "is_correct": False},
                    {"label": "D", "text": "`is.null()` returns TRUE for a vector containing an element defined as `NA`.", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "In R, NA is a placeholder for missing values and retains a mode (e.g., NA_integer_, NA_real_), possessing length 1. In contrast, NULL represents the empty object, has length 0, and cannot be an element of an atomic vector.",
                "model_answer": "Correct Option: A.\n\nExplanation: In R, NA is a placeholder for missing values and retains a mode (e.g., NA_integer_, NA_real_), possessing length 1. In contrast, NULL represents the empty object, has length 0, and cannot be an element of an atomic vector.",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. NA denotes missing values and has length 1, while NULL represents the null object of length 0.",
                    "B": "Incorrect. NA has length 1, whereas NULL has length 0.",
                    "C": "Incorrect. NULL cannot be stored in an atomic vector; doing so drops the element.",
                    "D": "Incorrect. is.null(NA) returns FALSE."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            },
            {
                "topic": "Vector Element names",
                "stem": "Which R function is used to assign or retrieve the names of elements in a vector?",
                "options": [
                    {"label": "A", "text": "`colnames()`", "is_correct": False},
                    {"label": "B", "text": "`names()`", "is_correct": True},
                    {"label": "C", "text": "`labels()`", "is_correct": False},
                    {"label": "D", "text": "`dimnames()`", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "The `names()` function accesses and sets the 'names' attribute of an atomic vector or list in R.",
                "model_answer": "Correct Option: B.\n\nExplanation: The `names()` function accesses and sets the 'names' attribute of an atomic vector or list in R.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. colnames() is used for two-dimensional structures like matrices and data frames.",
                    "B": "Correct. names() is the built-in function for 1D vectors and lists.",
                    "C": "Incorrect. labels() extracts term labels from model formulas.",
                    "D": "Incorrect. dimnames() provides dimension names for arrays and matrices."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            }
        ],
        "programming": [
            {
                "topic": "Common Vector operations",
                "stem": "Write an R script to create a numeric vector containing values from 1 to 50. Filter out all odd numbers, compute the cumulative sum of the remaining even numbers, and display the final result with appropriate element names.",
                "model_answer": "```R\n# 1. Generate sequence 1 to 50\nvec <- 1:50\n\n# 2. Filter even numbers\neven_vec <- vec[vec %% 2 == 0]\n\n# 3. Compute cumulative sum\ncum_res <- cumsum(even_vec)\n\n# 4. Assign element names\nnames(cum_res) <- paste0('E_', seq_along(cum_res))\n\n# Display output\nprint(cum_res)\n```",
                "marking_scheme": "3 Marks: Vector creation and modular filtering using %% operator\n4 Marks: Correct usage of cumsum() and naming with paste0()\n3 Marks: Execution syntax, code comments, and output display",
                "bloom": "L3 - Apply",
                "marks": 10,
                "difficulty": "Medium"
            },
            {
                "topic": "Vectors and Matrices",
                "stem": "Write an R program to construct a 4x4 matrix initialized with integer values 1 to 16 arranged by row. Extract the primary diagonal elements, compute the column-wise sums using colSums(), and replace all elements strictly greater than 10 with zero.",
                "model_answer": "```R\n# 1. Construct 4x4 matrix by row\nmat <- matrix(1:16, nrow = 4, ncol = 4, byrow = TRUE)\n\n# 2. Extract primary diagonal\ndiag_elements <- diag(mat)\n\n# 3. Column-wise sums\ncol_sums <- colSums(mat)\n\n# 4. Conditional element replacement\nmat[mat > 10] <- 0\n\nprint(mat)\nprint(diag_elements)\nprint(col_sums)\n```",
                "marking_scheme": "4 Marks: Matrix construction with nrow, ncol, and byrow\n3 Marks: Diagonal extraction with diag() and colSums() computation\n3 Marks: Logical indexing and conditional replacement",
                "bloom": "L3 - Apply",
                "marks": 10,
                "difficulty": "Medium"
            }
        ],
        "descriptive": [
            {
                "topic": "Introduction to R",
                "stem": "Explain the features of R and describe the steps involved in creating, executing and saving an R script with suitable examples.",
                "model_answer": "1. Core Features of R: R is an interpreted, open-source programming language designed for statistical computing and graphics. Key features include vectorized arithmetic, comprehensive package ecosystem (CRAN), native matrix and data frame structures, dynamic typing, and functional programming capabilities.\n2. Creating an R Script: An R script is an ASCII text file with a .R extension containing sequential R expressions. Created via `file.edit('analysis.R')` or any IDE text editor.\n3. Execution Methods: Executed interactively using `source('analysis.R')` in the R console, or non-interactively from the shell using `Rscript analysis.R`.\n4. Saving Workspace & Outputs: Workspace state is saved via `save.image('project.RData')`, individual objects via `save(obj, file='obj.rda')`, and graphics via `png()`, `pdf()`, and `dev.off()`.",
                "marking_scheme": "4 Marks: Comprehensive explanation of R's statistical features\n5 Marks: Step-by-step procedure for creating, sourcing, and executing scripts with examples\n4 Marks: Methods for saving workspace images, objects, and external outputs",
                "bloom": "L2 - Understand",
                "marks": 13,
                "difficulty": "Medium"
            },
            {
                "topic": "Vectorized operations",
                "stem": "Distinguish between vectorized operations and scalar iterations using loops in R. Illustrate your answer with execution examples comparing their syntax and computational performance.",
                "model_answer": "1. Vectorized Operations: Built-in R functions operate on entire vectors simultaneously without explicit iteration, implemented in underlying optimized C and Fortran routines (e.g., `x + y` or `ifelse(x > 0, 1, -1)`).\n2. Iterative Loops: Explicit `for` or `while` loops incur dynamic type-checking overhead and memory reallocation on each iteration.\n3. Code Illustration:\n```R\n# Vectorized addition\nz <- x + y\n\n# Equivalent iterative loop\nz <- numeric(length(x))\nfor(i in seq_along(x)) {\n  z[i] <- x[i] + y[i]\n}\n```\n4. Performance Considerations: Vectorization provides significant speedups and concise code, avoiding explicit index management.",
                "marking_scheme": "4 Marks: Conceptual distinction between vectorized operations and loops\n5 Marks: Code snippets contrasting both approaches\n4 Marks: Analysis of computational efficiency and memory allocation",
                "bloom": "L4 - Analyze",
                "marks": 13,
                "difficulty": "Medium"
            }
        ]
    },
    "2": {
        "unit_title": "Matrices, Arrays And Lists",
        "co": "CO2",
        "mcq": [
            {
                "topic": "Matrix operations",
                "stem": "Which operator is used to perform standard matrix multiplication between two compatible matrices `A` and `B` in R?",
                "options": [
                    {"label": "A", "text": "`*`", "is_correct": False},
                    {"label": "B", "text": "`%*%`", "is_correct": True},
                    {"label": "C", "text": "`%.%`", "is_correct": False},
                    {"label": "D", "text": "`**`", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "In R, `%*%` denotes matrix multiplication, requiring that the number of columns in A matches the number of rows in B. The standard `*` operator performs element-wise multiplication.",
                "model_answer": "Correct Option: B.\n\nExplanation: In R, `%*%` denotes matrix multiplication, requiring that the number of columns in A matches the number of rows in B. The standard `*` operator performs element-wise multiplication.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. * executes element-wise Hadamard multiplication.",
                    "B": "Correct. %*% is R's inner-product matrix multiplication operator.",
                    "C": "Incorrect. %.% is not a valid built-in matrix operator in R.",
                    "D": "Incorrect. ** is an exponentiation operator in R."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            },
            {
                "topic": "Avoiding Dimension Reduction",
                "stem": "When extracting a single row or column from an R matrix `M`, how can you prevent R from automatically reducing the resulting object into a 1D vector?",
                "options": [
                    {"label": "A", "text": "By passing the argument `drop = FALSE` inside the index bracket (e.g., `M[1, , drop = FALSE]`).", "is_correct": True},
                    {"label": "B", "text": "By setting `options(reduce = FALSE)` in the active R session.", "is_correct": False},
                    {"label": "C", "text": "By applying the `as.matrix()` function after slicing.", "is_correct": False},
                    {"label": "D", "text": "By using double square brackets `M[[1, ]]`.", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "By default, R subscripts matrix dimensions with `drop = TRUE`, reducing 1xN or Nx1 slices to a simple vector. Passing `drop = FALSE` instructs R to preserve the two-dimensional matrix structure and its attributes.",
                "model_answer": "Correct Option: A.\n\nExplanation: By default, R subscripts matrix dimensions with `drop = TRUE`, reducing 1xN or Nx1 slices to a simple vector. Passing `drop = FALSE` instructs R to preserve the two-dimensional matrix structure and its attributes.",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. drop = FALSE retains the matrix class and dimension attributes.",
                    "B": "Incorrect. No such global option exists in base R.",
                    "C": "Incorrect. Slicing with drop=TRUE strips row/col attributes before as.matrix() can recover original orientation.",
                    "D": "Incorrect. Double square brackets [[ ]] are for single element selection in recursive lists."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            },
            {
                "topic": "Applying Functions to Matrix Rows and Columns",
                "stem": "To apply a summary function `mean` across every column of a numeric matrix `X`, which `apply()` call is correct?",
                "options": [
                    {"label": "A", "text": "`apply(X, MARGIN = 1, FUN = mean)`", "is_correct": False},
                    {"label": "B", "text": "`apply(X, MARGIN = 2, FUN = mean)`", "is_correct": True},
                    {"label": "C", "text": "`apply(X, MARGIN = c(1, 2), FUN = mean)`", "is_correct": False},
                    {"label": "D", "text": "`lapply(X, FUN = mean)`", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "In the `apply(X, MARGIN, FUN)` function, `MARGIN = 1` indicates rows, while `MARGIN = 2` indicates columns. Therefore, `apply(X, 2, mean)` computes column means.",
                "model_answer": "Correct Option: B.\n\nExplanation: In the `apply(X, MARGIN, FUN)` function, `MARGIN = 1` indicates rows, while `MARGIN = 2` indicates columns. Therefore, `apply(X, 2, mean)` computes column means.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. MARGIN = 1 computes summary values across rows.",
                    "B": "Correct. MARGIN = 2 designates column-wise application.",
                    "C": "Incorrect. MARGIN = c(1, 2) applies the function to each individual cell.",
                    "D": "Incorrect. lapply treats the matrix as an underlying vector rather than preserving column boundaries."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            }
        ],
        "programming": [
            {
                "topic": "Matrix operations",
                "stem": "Write an R program to create two compatible matrices and perform addition, multiplication, transposition and element-wise operations. Explain each step and display the resulting matrices.",
                "model_answer": "```R\n# Step 1: Create two 3x3 compatible numeric matrices\nA <- matrix(c(1, 2, 3, 4, 5, 6, 7, 8, 9), nrow = 3, ncol = 3, byrow = TRUE)\nB <- matrix(c(9, 8, 7, 6, 5, 4, 3, 2, 1), nrow = 3, ncol = 3, byrow = TRUE)\n\n# Step 2: Matrix Addition\nmat_add <- A + B\nprint('Matrix Addition (A + B):')\nprint(mat_add)\n\n# Step 3: Element-wise Multiplication (Hadamard Product)\nelem_mult <- A * B\nprint('Element-wise Multiplication (A * B):')\nprint(elem_mult)\n\n# Step 4: True Matrix Multiplication\nmat_mult <- A %*% B\nprint('Matrix Multiplication (A %*% B):')\nprint(mat_mult)\n\n# Step 5: Transposition of Matrix A\nmat_trans <- t(A)\nprint('Transpose of A (t(A)):')\nprint(mat_trans)\n```",
                "marking_scheme": "3 Marks: Matrix initialization using matrix() with proper dimensions\n3 Marks: Implementation of matrix addition and element-wise product\n4 Marks: Implementation of matrix multiplication (%*%) and transpose t()\n3 Marks: Clear explanation of operational mechanisms and output display",
                "bloom": "L3 - Apply",
                "marks": 13,
                "difficulty": "Medium"
            },
            {
                "topic": "Applying Functions to Matrix Rows and Columns",
                "stem": "Write an R script that initializes a 5x4 matrix with random integers from 10 to 100. Using the `apply()` function, calculate the row sums, column standard deviations, and normalize each row by subtracting its mean. Display all intermediate and final outputs.",
                "model_answer": "```R\nset.seed(42)\nM <- matrix(sample(10:100, 20, replace = TRUE), nrow = 5, ncol = 4)\n\n# 1. Row sums using apply()\nrow_s <- apply(M, 1, sum)\n\n# 2. Column standard deviations using apply()\ncol_sd <- apply(M, 2, sd)\n\n# 3. Row normalization: subtract row mean\nrow_means <- apply(M, 1, mean)\nnorm_M <- t(apply(M, 1, function(r) r - mean(r)))\n\nprint('Original Matrix:'); print(M)\nprint('Row Sums:'); print(row_s)\nprint('Column SDs:'); print(col_sd)\nprint('Row-Normalized Matrix:'); print(norm_M)\n```",
                "marking_scheme": "3 Marks: Random matrix generation with sample() and set.seed()\n3 Marks: Row sum and column standard deviation calculation using apply()\n4 Marks: Row normalization logic and handling transposition after apply()\n3 Marks: Code readability, comments, and formatted output verification",
                "bloom": "L3 - Apply",
                "marks": 13,
                "difficulty": "Medium"
            }
        ],
        "descriptive": [
            {
                "topic": "Creating lists",
                "stem": "Explain the characteristics of lists in R and discuss how they differ from atomic vectors and matrices. Describe the operations used to create, index, and apply functions to recursive lists with code examples.",
                "model_answer": "1. Definition & Structure: Lists are recursive vectors whose components can be of heterogeneous modes, including vectors, matrices, data frames, or other nested lists.\n2. Contrast with Atomic Vectors & Matrices: Atomic vectors and matrices require strict homogeneous data types. In contrast, lists allow diverse data structures under a single container.\n3. Indexing Modes:\n- Single Bracket `list[i]`: Returns a sub-list of length 1.\n- Double Bracket `list[[i]]`: Extracts the actual component stored inside.\n- Dollar Operator `list$name`: Accesses named component directly.\n4. Applying Functions: `lapply()` applies a function and returns a list; `sapply()` attempts to simplify the output into an atomic vector or matrix.",
                "marking_scheme": "4 Marks: Conceptual distinction between lists, atomic vectors, and matrices\n5 Marks: Detailed explanation of indexing operators ([], [[]], $) with examples\n4 Marks: Discussion of recursive lists and function application via lapply/sapply",
                "bloom": "L4 - Analyze",
                "marks": 13,
                "difficulty": "Medium"
            }
        ]
    },
    "3": {
        "unit_title": "Data Frames",
        "co": "CO3",
        "mcq": [
            {
                "topic": "Merging Data Frames",
                "stem": "In base R, which function is used to combine two data frames based on one or more common key columns?",
                "options": [
                    {"label": "A", "text": "`cbind()`", "is_correct": False},
                    {"label": "B", "text": "`merge()`", "is_correct": True},
                    {"label": "C", "text": "`join()`", "is_correct": False},
                    {"label": "D", "text": "`rbind()`", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "The `merge()` function performs relational database-style joins (inner, outer, left, right) between two data frames based on shared key variables (by, by.x, by.y).",
                "model_answer": "Correct Option: B.\n\nExplanation: The `merge()` function performs relational database-style joins (inner, outer, left, right) between two data frames based on shared key variables (by, by.x, by.y).",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. cbind() combines columns side-by-side without checking relational keys.",
                    "B": "Correct. merge() performs key-based relational joins on data frames.",
                    "C": "Incorrect. join() is not in base R (it belongs to the plyr/dplyr packages).",
                    "D": "Incorrect. rbind() stacks data frames row-wise requiring identical column names."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            },
            {
                "topic": "Factors and Tables",
                "stem": "What is the primary role of the `levels` attribute in an R factor variable?",
                "options": [
                    {"label": "A", "text": "It stores the underlying memory addresses of the data frame.", "is_correct": False},
                    {"label": "B", "text": "It defines the complete set of valid discrete categorical values that the factor can represent.", "is_correct": True},
                    {"label": "C", "text": "It determines whether the factor allows floating-point numerical operations.", "is_correct": False},
                    {"label": "D", "text": "It converts the categorical values into continuous probability densities.", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "A factor in R represents categorical data stored internally as integer codes. The `levels` attribute contains the character labels corresponding to these integer codes, defining permissible categories.",
                "model_answer": "Correct Option: B.\n\nExplanation: A factor in R represents categorical data stored internally as integer codes. The `levels` attribute contains the character labels corresponding to these integer codes, defining permissible categories.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. Levels represent categorical categories, not memory pointers.",
                    "B": "Correct. Levels delineate the discrete categories and their ordering.",
                    "C": "Incorrect. Factors are categorical and cannot directly undergo continuous math.",
                    "D": "Incorrect. Levels do not calculate probability density functions."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            },
            {
                "topic": "Environment and Scope issues",
                "stem": "Which operator in R is used to perform assignment in the enclosing parent environment (superassignment)?",
                "options": [
                    {"label": "A", "text": "`<-`", "is_correct": False},
                    {"label": "B", "text": "`<<-`", "is_correct": True},
                    {"label": "C", "text": "`:=`", "is_correct": False},
                    {"label": "D", "text": "`->>`", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "The `<<-` superassignment operator searches through enclosing parent environments to rebind an existing variable or creates it in the global environment if not found.",
                "model_answer": "Correct Option: B.\n\nExplanation: The `<<-` superassignment operator searches through enclosing parent environments to rebind an existing variable or creates it in the global environment if not found.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. <- assigns variables only within the local execution environment.",
                    "B": "Correct. <<- performs superassignment across enclosing lexical scopes.",
                    "C": "Incorrect. := is used for in-place assignment in data.table.",
                    "D": "Incorrect. ->> is rightward superassignment, less standard in scoping literature."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            }
        ],
        "programming": [
            {
                "topic": "Merging Data Frames",
                "stem": "Write an R program to create two data frames: one containing student academic details (StudentID, Name, Department) and another containing examination results (StudentID, CourseCode, Marks). Perform an inner join and a full outer join using `merge()`. Filter students scoring greater than 75 marks.",
                "model_answer": "```R\n# Create Student Info DataFrame\nstudents <- data.frame(\n  StudentID = c(101, 102, 103, 104),\n  Name = c('Alice', 'Bob', 'Charlie', 'David'),\n  Department = c('CSE', 'ECE', 'CSE', 'IT'),\n  stringsAsFactors = FALSE\n)\n\n# Create Exam Results DataFrame\nresults <- data.frame(\n  StudentID = c(101, 102, 103, 105),\n  CourseCode = c('CS204', 'CS204', 'CS204', 'CS204'),\n  Marks = c(88, 64, 92, 70)\n)\n\n# 1. Inner Join using merge()\ninner_df <- merge(students, results, by = 'StudentID')\nprint('Inner Join:'); print(inner_df)\n\n# 2. Full Outer Join using merge()\nouter_df <- merge(students, results, by = 'StudentID', all = TRUE)\nprint('Full Outer Join:'); print(outer_df)\n\n# 3. Filter students with Marks > 75\nhonors <- inner_df[inner_df$Marks > 75, c('StudentID', 'Name', 'Marks')]\nprint('Students scoring > 75:'); print(honors)\n```",
                "marking_scheme": "3 Marks: Construction of realistic data frames with appropriate data types\n4 Marks: Accurate implementation of inner join and full outer join (all = TRUE)\n3 Marks: Logical indexing and column subsetting for Marks > 75\n3 Marks: Explanation of output differences and handling of unmatched keys",
                "bloom": "L3 - Apply",
                "marks": 13,
                "difficulty": "Medium"
            },
            {
                "topic": "Data frames and Factor processing",
                "stem": "Write an R script to create a data frame of employees with columns `EmpID`, `Department` (as a factor with 3 distinct levels), and `MonthlySalary`. Compute the mean salary by department using `aggregate()` or `tapply()`, and add a new boolean column indicating whether each employee's salary exceeds their department's median.",
                "model_answer": "```R\n# 1. Create data frame\nemployees <- data.frame(\n  EmpID = 1:6,\n  Department = factor(c('Sales', 'Eng', 'Sales', 'HR', 'Eng', 'HR')),\n  MonthlySalary = c(45000, 75000, 52000, 48000, 82000, 51000)\n)\n\n# 2. Mean salary by department using aggregate\ndept_mean <- aggregate(MonthlySalary ~ Department, data = employees, FUN = mean)\nprint('Department Mean Salaries:'); print(dept_mean)\n\n# 3. Add column comparing to department median using ave()\nemployees$AboveDeptMedian <- employees$MonthlySalary > ave(employees$MonthlySalary, employees$Department, FUN = median)\nprint('Enriched Employee Records:'); print(employees)\n```",
                "marking_scheme": "4 Marks: Data frame creation with properly typed factor levels\n4 Marks: Aggregation of salaries by department using aggregate() or tapply()\n3 Marks: Vectorized conditional calculation with ave() or split-apply\n2 Marks: Output verification and syntax correctness",
                "bloom": "L3 - Apply",
                "marks": 13,
                "difficulty": "Medium"
            }
        ],
        "descriptive": [
            {
                "topic": "Factors and Tables",
                "stem": "Explain the internal representation and utility of factors in R. Describe how frequency tables and cross-tabulations are constructed and analyzed using `table()`, `prop.table()`, and `margin.table()` with practical code demonstrations.",
                "model_answer": "1. Factor Internal Architecture: Factors store discrete categorical data as integer vectors with an attached 'levels' character attribute, optimizing memory storage and ensuring standardized levels for statistical modeling.\n2. Construction of Frequency Tables: The `table()` function counts frequencies across categorical levels.\n3. Proportions and Margins:\n- `prop.table(tbl)`: Converts cell counts into relative proportions.\n- `margin.table(tbl, margin)`: Computes marginal sums across rows (1) or columns (2).\n4. Code Demonstration:\n```R\ngender <- factor(c('M', 'F', 'F', 'M', 'F'))\ngrade <- factor(c('A', 'B', 'A', 'C', 'B'))\ntbl <- table(gender, grade)\nprop <- prop.table(tbl, 1) # row proportions\n```",
                "marking_scheme": "4 Marks: Architectural explanation of factors and integer encoding\n5 Marks: Demonstration of table(), prop.table(), and margin.table()\n4 Marks: Practical statistical interpretation of categorical contingency tables",
                "bloom": "L4 - Analyze",
                "marks": 13,
                "difficulty": "Medium"
            }
        ]
    },
    "4": {
        "unit_title": "Oop",
        "co": "CO4",
        "mcq": [
            {
                "topic": "S3 Classes",
                "stem": "How does R's S3 object system determine which specific method to dispatch for a generic function like `print()`?",
                "options": [
                    {"label": "A", "text": "By inspecting the `class` attribute of the primary argument and invoking `generic.classname()` via `UseMethod()`.", "is_correct": True},
                    {"label": "B", "text": "By compiling a dispatch lookup table via strict XML schema definitions.", "is_correct": False},
                    {"label": "C", "text": "By checking the slot names declared inside `setClass()`.", "is_correct": False},
                    {"label": "D", "text": "By executing all methods defined in the global environment sequentially.", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "S3 relies on single dispatch implemented through `UseMethod('generic')`. It checks the class attribute of the first argument and looks for a function named `generic.classname` (e.g. print.data.frame).",
                "model_answer": "Correct Option: A.\n\nExplanation: S3 relies on single dispatch implemented through `UseMethod('generic')`. It checks the class attribute of the first argument and looks for a function named `generic.classname` (e.g. print.data.frame).",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. UseMethod() matches the generic name with the object's class attribute.",
                    "B": "Incorrect. S3 is dynamic and informal, with no XML compilation.",
                    "C": "Incorrect. setClass() belongs to the formal S4 object-oriented system.",
                    "D": "Incorrect. R uses deterministic method dispatch based on inheritance order."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            },
            {
                "topic": "reading and writing files",
                "stem": "Which base R function is optimized for reading comma-separated values (CSV) files into a data frame?",
                "options": [
                    {"label": "A", "text": "`read.table()` with `sep = ','` (or `read.csv()`)", "is_correct": True},
                    {"label": "B", "text": "`scan()` with `what = 'binary'`", "is_correct": False},
                    {"label": "C", "text": "`load()`", "is_correct": False},
                    {"label": "D", "text": "`source()`", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "`read.csv()` is a wrapper for `read.table()` configured with `sep = ','` and `header = TRUE`, specifically designed to read comma-separated text files into a data frame.",
                "model_answer": "Correct Option: A.\n\nExplanation: `read.csv()` is a wrapper for `read.table()` configured with `sep = ','` and `header = TRUE`, specifically designed to read comma-separated text files into a data frame.",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. read.csv() and read.table(..., sep=',') are standard CSV readers.",
                    "B": "Incorrect. scan() reads raw vectors rather than structuring data frames.",
                    "C": "Incorrect. load() reloads binary .RData files into the workspace.",
                    "D": "Incorrect. source() reads and parses R code scripts."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            },
            {
                "topic": "Graphics",
                "stem": "Which sequence of functions correctly creates a scatter plot and saves it as a high-resolution PNG image file in base R?",
                "options": [
                    {"label": "A", "text": "`png('plot.png')` followed by `plot(x, y)` and `dev.off()`.", "is_correct": True},
                    {"label": "B", "text": "`plot(x, y)` followed by `save.image('plot.png')`.", "is_correct": False},
                    {"label": "C", "text": "`export.graphics(plot(x, y), file = 'plot.png')`.", "is_correct": False},
                    {"label": "D", "text": "`render('plot.png')` followed by `plot(x, y)`.", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "In R graphics, opening a device driver (e.g., `png('file.png')`), executing plotting functions, and finally closing the device with `dev.off()` flushes and saves the graphical file.",
                "model_answer": "Correct Option: A.\n\nExplanation: In R graphics, opening a device driver (e.g., `png('file.png')`), executing plotting functions, and finally closing the device with `dev.off()` flushes and saves the graphical file.",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. png() initializes device, plot() draws, dev.off() closes and saves.",
                    "B": "Incorrect. save.image() saves workspace variables, not graphic devices.",
                    "C": "Incorrect. export.graphics() is not a built-in base R function.",
                    "D": "Incorrect. render() is from R Markdown / Shiny, not base graphics driver."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            }
        ],
        "programming": [
            {
                "topic": "reading and writing files",
                "stem": "Compare the functions used to read and write text, CSV and tabular data in R. Analyze their suitability for different file formats and illustrate your answer with appropriate code.",
                "model_answer": "```R\n# 1. Reading & Writing CSV files\ndata(iris)\nwrite.csv(iris, file = 'iris_data.csv', row.names = FALSE)\ncsv_data <- read.csv('iris_data.csv', header = TRUE)\n\n# 2. Reading & Writing General Delimited Tabular Data\nwrite.table(iris, file = 'iris_tab.txt', sep = '\\t', row.names = FALSE)\ntab_data <- read.table('iris_tab.txt', header = TRUE, sep = '\\t')\n\n# 3. Fast line-by-line reading for unstructured text\ncat('Line 1: Summary\\nLine 2: Observations', file = 'notes.txt')\nlines <- readLines('notes.txt')\n\n# Comparison Analysis:\n# - read.csv(): Optimized for comma-delimited data with headers.\n# - read.table(): Flexible for arbitrary delimiters (tab, semicolon, space).\n# - readLines(): Ideal for non-tabular text logs and arbitrary line structures.\n```",
                "marking_scheme": "4 Marks: Demonstration of read.csv() and write.csv() with parameter options\n4 Marks: Implementation of read.table() with tab-delimited formatting\n3 Marks: Explanation of readLines() for unstructured textual input\n2 Marks: Analytical comparison of format suitability, memory efficiency, and speed",
                "bloom": "L4 - Analyze",
                "marks": 13,
                "difficulty": "Medium"
            },
            {
                "topic": "S3 Classes",
                "stem": "Demonstrate the implementation of an S3 object-oriented system in R. Create a constructor for a student record class, implement a custom `print` method, and define a generic function with class-specific method dispatch.",
                "model_answer": "```R\n# 1. S3 Constructor Function\nmake_student <- function(id, name, gpa) {\n  obj <- list(id = id, name = name, gpa = gpa)\n  class(obj) <- 'student_record'\n  return(obj)\n}\n\n# 2. S3 Method for generic print()\nprint.student_record <- function(x, ...) {\n  cat('=== Student Record ===\\n')\n  cat('ID:  ', x$id, '\\n')\n  cat('Name:', x$name, '\\n')\n  cat('GPA: ', round(x$gpa, 2), '\\n')\n}\n\n# 3. Custom Generic and Method\nstanding <- function(x) UseMethod('standing')\nstanding.student_record <- function(x) {\n  if (x$gpa >= 3.5) 'Dean\\'s Honors' else 'Good Standing'\n}\n\n# Verification\ns1 <- make_student(101, 'Robert Green', 3.8)\nprint(s1)\ncat('Status:', standing(s1), '\\n')\n```",
                "marking_scheme": "4 Marks: Constructor design with list structure and class attribute assignment\n4 Marks: Implementation of custom print.student_record method\n3 Marks: Defining generic function with UseMethod() and specific dispatch\n2 Marks: Code execution trace and verification output",
                "bloom": "L3 - Apply",
                "marks": 13,
                "difficulty": "Medium"
            }
        ],
        "descriptive": [
            {
                "topic": "S3 Classes",
                "stem": "Compare the S3 and S4 object systems in R using appropriate architectural criteria. Discuss their differences in formal class definition, type validation, method dispatch, and slot encapsulation.",
                "model_answer": "1. S3 System (Informal OOP):\n- Class declaration is informal; set via `class(x) <- 'name'`.\n- Attributes accessed via `$` or `attr()`.\n- Single dispatch implemented using `UseMethod()`.\n- Lacks rigorous compile-time type validation or schema enforcement.\n\n2. S4 System (Formal OOP):\n- Formal class definition using `setClass()` specifying slot types.\n- Slots accessed via `@` operator.\n- Supports multiple dispatch using `setGeneric()` and `setMethod()`.\n- Enforces strict validation rules via `validObject()`.\n\n3. Comparative Evaluation:\n- S3 is lightweight, highly intuitive, and widespread in base R.\n- S4 is robust, safer for large complex packages (Bioconductor), but introduces runtime overhead.",
                "marking_scheme": "4 Marks: Detailed analysis of S3 informal mechanics and single dispatch\n5 Marks: Detailed analysis of S4 formal class definition, slots, and multiple dispatch\n4 Marks: Comparison matrix evaluating safety, flexibility, and architectural overhead",
                "bloom": "L4 - Analyze",
                "marks": 13,
                "difficulty": "Medium"
            }
        ]
    },
    "5": {
        "unit_title": "Interfacing",
        "co": "CO5",
        "mcq": [
            {
                "topic": "Generalized Linear models",
                "stem": "In R, which function is used to specify and fit a Generalized Linear Model (GLM) for binary logistic regression?",
                "options": [
                    {"label": "A", "text": "`lm(y ~ x, method = 'logistic')`", "is_correct": False},
                    {"label": "B", "text": "`glm(y ~ x, family = binomial(link = 'logit'))`", "is_correct": True},
                    {"label": "C", "text": "`nls(y ~ x, family = 'binary')`", "is_correct": False},
                    {"label": "D", "text": "`logistic.fit(x, y)`", "is_correct": False}
                ],
                "correct": "B",
                "explanation": "The `glm()` function fits generalized linear models in R. Specifying `family = binomial(link = 'logit')` configures the model for binary logistic regression.",
                "model_answer": "Correct Option: B.\n\nExplanation: The `glm()` function fits generalized linear models in R. Specifying `family = binomial(link = 'logit')` configures the model for binary logistic regression.",
                "marking_scheme": "2 Marks: Selecting the correct option (B) based on technical reasoning.",
                "distractors": {
                    "A": "Incorrect. lm() fits standard linear models under Gaussian assumptions.",
                    "B": "Correct. glm() with family = binomial fits binary logistic models.",
                    "C": "Incorrect. nls() fits nonlinear least squares models.",
                    "D": "Incorrect. logistic.fit() is not a base R function."
                },
                "bloom": "L2 - Understand",
                "difficulty": "Easy"
            },
            {
                "topic": "Clustering",
                "stem": "Which R function performs standard K-means clustering on a numeric matrix or data frame?",
                "options": [
                    {"label": "A", "text": "`kmeans()`", "is_correct": True},
                    {"label": "B", "text": "`hclust()`", "is_correct": False},
                    {"label": "C", "text": "`cluster.tree()`", "is_correct": False},
                    {"label": "D", "text": "`kmedoids()`", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "The base `stats` package provides `kmeans(x, centers = k, nstart = 25)` to partition data into k distinct clusters.",
                "model_answer": "Correct Option: A.\n\nExplanation: The base `stats` package provides `kmeans(x, centers = k, nstart = 25)` to partition data into k distinct clusters.",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. kmeans() executes the Lloyd/Hartigan-Wong K-means partitioning algorithm.",
                    "B": "Incorrect. hclust() performs hierarchical agglomerative clustering.",
                    "C": "Incorrect. cluster.tree() is not a built-in R clustering function.",
                    "D": "Incorrect. kmedoids is in the cluster package under pam()."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            },
            {
                "topic": "Linear Model",
                "stem": "When evaluating a fitted linear model `model <- lm(y ~ x)`, which function displays the estimated coefficients, standard errors, t-statistics, p-values, and R-squared metric?",
                "options": [
                    {"label": "A", "text": "`summary(model)`", "is_correct": True},
                    {"label": "B", "text": "`anova(model)`", "is_correct": False},
                    {"label": "C", "text": "`coef(model)`", "is_correct": False},
                    {"label": "D", "text": "`residuals(model)`", "is_correct": False}
                ],
                "correct": "A",
                "explanation": "`summary(model)` generates a comprehensive statistical summary of the fitted model, including parameter estimates, standard errors, t-values, p-values, residual standard error, and R-squared.",
                "model_answer": "Correct Option: A.\n\nExplanation: `summary(model)` generates a comprehensive statistical summary of the fitted model, including parameter estimates, standard errors, t-values, p-values, residual standard error, and R-squared.",
                "marking_scheme": "2 Marks: Selecting the correct option (A) based on technical reasoning.",
                "distractors": {
                    "A": "Correct. summary() provides the complete statistical breakdown of the regression.",
                    "B": "Incorrect. anova() produces an analysis of variance table.",
                    "C": "Incorrect. coef() returns only the raw estimated beta coefficients.",
                    "D": "Incorrect. residuals() extracts the individual residual errors."
                },
                "bloom": "L1 - Remember",
                "difficulty": "Easy"
            }
        ],
        "programming": [
            {
                "topic": "Generalized Linear models",
                "stem": "Evaluate the suitability of a generalized linear model for predicting a binary outcome. Justify the choice of distribution and link function, and explain how model performance can be assessed in R.",
                "model_answer": "```R\n# 1. Dataset Generation & Model Fitting\ndata(mtcars)\n# Predict transmission type (am: 0 = automatic, 1 = manual)\n# using engine horsepower (hp) and weight (wt)\nlogit_model <- glm(am ~ hp + wt, data = mtcars, family = binomial(link = 'logit'))\n\n# 2. Model Summary & Coefficients\nsummary(logit_model)\n\n# 3. Model Interpretation (Odds Ratios)\nodds_ratios <- exp(coef(logit_model))\nprint('Odds Ratios:'); print(odds_ratios)\n\n# 4. Model Evaluation & Performance\n# AIC, Residual Deviance vs Null Deviance\nnull_dev <- logit_model$null.deviance\nres_dev <- logit_model$deviance\npseudo_r2 <- 1 - (res_dev / null_dev)\ncat('McFadden Pseudo R-squared:', round(pseudo_r2, 4), '\\n')\n```",
                "marking_scheme": "4 Marks: Mathematical justification of binomial family and logit link function\n4 Marks: Correct glm() formulation and parameter estimation\n3 Marks: Calculation of Odds Ratios using exp(coef()) and confidence intervals\n2 Marks: Model diagnostics via residual deviance, AIC, and confusion matrix",
                "bloom": "L5 - Evaluate",
                "marks": 13,
                "difficulty": "Hard"
            },
            {
                "topic": "Clustering",
                "stem": "Write an R script to perform K-means clustering on the numeric columns of the `iris` dataset. Standardize the variables, determine the optimal number of clusters using the within-cluster sum of squares (elbow method), fit the final model with 3 clusters, and visualize the cluster assignments.",
                "model_answer": "```R\n# 1. Data Preparation\ndata(iris)\nx <- scale(iris[, 1:4])\n\n# 2. Elbow Method for Optimal K\nwcss <- numeric(10)\nset.seed(123)\nfor (k in 1:10) {\n  wcss[k] <- kmeans(x, centers = k, nstart = 20)$tot.withinss\n}\n\n# 3. Fit K-means with k = 3\nfinal_km <- kmeans(x, centers = 3, nstart = 25)\n\n# 4. Cluster Summary & Visualization\nprint(final_km$centers)\nplot(x[, 1:2], col = final_km$cluster, pch = 19, \n     main = 'K-Means Clustering on Iris Data (k=3)',\n     xlab = 'Sepal.Length (Standardized)', ylab = 'Sepal.Width (Standardized)')\npoints(final_km$centers[, 1:2], col = 1:3, pch = 8, cex = 2, lwd = 3)\n```",
                "marking_scheme": "3 Marks: Data scaling and pre-processing with scale()\n4 Marks: Implementation of loop calculating within-cluster sum of squares (elbow)\n3 Marks: K-means fitting with nstart parameter for stable local optima\n3 Marks: Visual scatter plot highlighting cluster centroids and labels",
                "bloom": "L3 - Apply",
                "marks": 13,
                "difficulty": "Medium"
            }
        ],
        "descriptive": [
            {
                "topic": "Linear Model",
                "stem": "Explain the theoretical assumptions underlying classical Ordinary Least Squares (OLS) linear regression. Describe how each assumption is diagnosed in R using residual plots, the Shapiro-Wilk test, and the Durbin-Watson statistic.",
                "model_answer": "1. OLS Core Assumptions:\n- Linearity: Relationship between predictors and response is linear in parameters.\n- Independence: Residual errors are uncorrelated.\n- Homoscedasticity: Constant variance of residuals across fitted values.\n- Normality: Residuals are normally distributed.\n- No Multicollinearity: Independent variables are not linearly redundant.\n\n2. Diagnostic Methods in R:\n- `plot(model, which = 1)`: Residuals vs Fitted tests linearity and homoscedasticity.\n- `plot(model, which = 2)`: Normal Q-Q plot assesses residual normality.\n- `shapiro.test(residuals(model))`: Formal statistical test for normality.\n- `car::durbinWatsonTest(model)`: Tests for first-order autocorrelation in residuals.\n- `car::vif(model)`: Assesses Variance Inflation Factor for multicollinearity.",
                "marking_scheme": "4 Marks: Detailed statement of all 5 classical OLS assumptions\n5 Marks: Demonstration of diagnostic plots (which = 1, 2) and interpretations\n4 Marks: Formal hypothesis testing using Shapiro-Wilk and Durbin-Watson in R",
                "bloom": "L4 - Analyze",
                "marks": 13,
                "difficulty": "Hard"
            }
        ],
        "design_application": [
            {
                "topic": "Interfacing",
                "stem": "Design an R-based statistical analysis workflow for a real-world dataset. Include data preparation, exploratory analysis, model selection, model fitting, validation and interpretation of results, with appropriate R functions.",
                "model_answer": "### Comprehensive R Statistical Analysis Workflow\n\n1. **Data Ingestion and Cleaning**:\n```R\n# Load dataset and inspect structures\ndata_raw <- read.csv('patient_clinical_records.csv', stringsAsFactors = FALSE)\ndim(data_raw); str(data_raw)\n\n# Handle missing values & convert categorical factors\nclean_data <- na.omit(data_raw)\nclean_data$outcome <- factor(clean_data$outcome, levels = c(0, 1), labels = c('Control', 'Case'))\n```\n\n2. **Exploratory Data Analysis (EDA)**:\n```R\n# Summary statistics and cross-tabulation\nsummary(clean_data)\ntable(clean_data$gender, clean_data$outcome)\n\n# Visualization: Distribution of biomarker by outcome group\nboxplot(biomarker ~ outcome, data = clean_data,\n        main = 'Biomarker Distribution by Clinical Outcome',\n        col = c('lightblue', 'salmon'), ylab = 'Biomarker Level')\n```\n\n3. **Model Selection & Fitting (GLM Formulation)**:\n```R\n# Fit Binary Logistic Regression Model\nfit_glm <- glm(outcome ~ age + biomarker + treatment_group,\n               data = clean_data, family = binomial(link = 'logit'))\nsummary(fit_glm)\n```\n\n4. **Model Diagnostics & Validation**:\n```R\n# Assess goodness-of-fit via deviance and McFadden Pseudo-R2\nnull_dev <- fit_glm$null.deviance\nres_dev <- fit_glm$deviance\nmcfadden <- 1 - (res_dev / null_dev)\ncat('McFadden Pseudo R2:', round(mcfadden, 4), '\\n')\n\n# Check Multicollinearity using Variance Inflation Factors\nlibrary(car)\nvif(fit_glm)\n```\n\n5. **Interpretation & Reporting**:\n```R\n# Compute Odds Ratios with 95% Confidence Intervals\nexp_coef <- exp(cbind(OR = coef(fit_glm), confint(fit_glm)))\nprint('Estimated Odds Ratios and 95% CI:'); print(exp_coef)\n```",
                "marking_scheme": "4 Marks: Data ingestion, missing-value mitigation, and factor encoding\n4 Marks: Exploratory visualization and distribution inspection using boxplot()\n4 Marks: Model fitting with glm() including binomial family and link function\n3 Marks: Diagnostic validation (Deviance, VIF) and clinical interpretation of Odds Ratios",
                "bloom": "L6 - Create",
                "marks": 15,
                "difficulty": "Hard"
            }
        ]
    }
}

def clean_supporting_passage(text: str) -> str:
    """Clean slide or page text to remove artifact headers and extract salient technical sentences."""
    if not text:
        return ""
    cleaned = re.sub(r'(?i)\b(slide\s*\d+|welcome|thank\s*you|agenda|presentation|unit\s*\d+)\b', '', text)
    lines = [l.strip() for l in cleaned.splitlines() if len(l.strip()) > 15]
    passage = " ".join(lines[:3])[:280] if lines else cleaned[:280]
    return passage.strip()

def synthesize_combined_type_question(
    unit: Dict[str, Any],
    topic: str,
    bloom_level: str,
    marks: int,
    co_level: str,
    types: List[str],
    mcq_config: Optional[Dict[str, Any]] = None,
    supporting_chunk: Optional[Dict[str, Any]] = None,
    used_questions: Optional[set] = None,
    existing_stems: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Synthesize a coherent combined-type question pairing two question types
    (e.g., Programming + Descriptive, Output Prediction + Debugging, Assertion + Numerical, Case Study + System Design)
    with explicit proportional mark allocation, unified prompt, separated model answers, and distinct marking rubrics.
    """
    if used_questions is None:
        used_questions = set()
    if existing_stems is None:
        existing_stems = []

    type_a = types[0] if types else "programming"
    type_b = types[1] if len(types) > 1 else "descriptive"
    combined_type_str = f"{type_a} + {type_b}"

    u_num = str(unit.get("number", "1"))
    u_title = unit.get("title", f"Unit {u_num}")
    topic_clean = topic or u_title

    # Proportional mark split
    if marks >= 10:
        marks_a = max(2, round(marks * 0.65))
        marks_b = marks - marks_a
    elif marks >= 5:
        marks_a = max(2, round(marks * 0.6))
        marks_b = marks - marks_a
    else:
        marks_a = 1
        marks_b = max(1, marks - 1)

    # Coherent Combination 1: Programming + Descriptive / Comparative
    if (type_a in ["programming", "coding"] and type_b in ["descriptive", "comparative_analysis", "concept_definition"]) or \
       (type_b in ["programming", "coding"] and type_a in ["descriptive", "comparative_analysis", "concept_definition"]):
        stem = (
            f"Part I (Programming - {marks_a} Marks):\n"
            f"Write a modular, fully commented R script/function to implement an end-to-end workflow for {topic_clean}. "
            f"Your code must handle vector inputs, validate data structures, and display the transformed results.\n\n"
            f"Part II (Descriptive - {marks_b} Marks):\n"
            f"Analyze the computational efficiency, vectorization mechanisms, and asymptotic memory trade-offs of your implementation "
            f"compared to iterative loops in base R."
        )
        model_ans = (
            f"### Part I: Programming Implementation ({marks_a} Marks)\n"
            f"```R\n"
            f"# 1. Function definition & validation\n"
            f"process_{re.sub(r'[^a-zA-Z0-9]', '_', topic_clean.lower())[:15]} <- function(data_input) {{\n"
            f"  if (is.null(data_input) || length(data_input) == 0) stop('Invalid input data')\n"
            f"  # Vectorized transformation\n"
            f"  res <- (data_input - mean(data_input, na.rm = TRUE)) / sd(data_input, na.rm = TRUE)\n"
            f"  return(res)\n"
            f"}}\n"
            f"# 2. Test Execution\n"
            f"test_vec <- c(10, 25, 30, 45, 50, 65)\n"
            f"out <- process_{re.sub(r'[^a-zA-Z0-9]', '_', topic_clean.lower())[:15]}(test_vec)\n"
            f"print(out)\n"
            f"```\n\n"
            f"### Part II: Conceptual & Trade-off Analysis ({marks_b} Marks)\n"
            f"1. Vectorization Rationale: Base R delegates operations to optimized underlying C routines, eliminating interpreter loop overhead.\n"
            f"2. Memory Allocation: Vectorized transforms avoid incremental reallocation inside iterative loops.\n"
            f"3. Complexity: Time complexity is O(N) compared to O(N^2) for improperly sized loop appends."
        )
        marking_sch = (
            f"Part I ({marks_a} Marks):\n"
            f"- {round(marks_a * 0.4, 1)} Marks: Correct R syntax, vectorized logic, and function structure\n"
            f"- {round(marks_a * 0.35, 1)} Marks: Input validation and edge-case handling\n"
            f"- {round(marks_a * 0.25, 1)} Marks: Execution test call and output verification\n\n"
            f"Part II ({marks_b} Marks):\n"
            f"- {round(marks_b * 0.5, 1)} Marks: In-depth analysis of vectorization vs iterative loops\n"
            f"- {round(marks_b * 0.5, 1)} Marks: Memory management, complexity trade-offs, and design justification"
        )
        rubric_crit = [
            {"criterion": f"Part I (Programming): R Implementation & Syntax", "marks": marks_a, "description": f"Robust script implementing {topic_clean} with vectorization and validation"},
            {"criterion": f"Part II (Descriptive): Architectural Analysis & Trade-offs", "marks": marks_b, "description": "Critical analysis of memory, vectorization overhead, and design alternatives"}
        ]

    # Coherent Combination 2: Output Prediction + Debugging
    elif (type_a in ["code_snippet_analysis", "output_prediction"] and type_b in ["debugging"]) or \
         (type_b in ["code_snippet_analysis", "output_prediction"] and type_a in ["debugging"]):
        stem = (
            f"Part I (Output Prediction - {marks_a} Marks):\n"
            f"Trace the execution of the following R code snippet on {topic_clean} and predict its exact console output:\n"
            f"```R\n"
            f"vec <- c(2, 4, 6, 8, 10)\n"
            f"res <- sapply(vec, function(x) if (x > 5) x^2 else x * 10)\n"
            f"names(res) <- paste0('K', seq_along(res))\n"
            f"print(res[res %% 4 == 0])\n"
            f"```\n\n"
            f"Part II (Code Debugging - {marks_b} Marks):\n"
            f"Identify any logical bugs, boundary issues, or edge cases where the snippet fails (e.g., when `vec` contains `NA` values or has zero length). "
            f"Explain why the defect manifests and provide the corrected, defensively written code."
        )
        model_ans = (
            f"### Part I: Execution Trace & Output ({marks_a} Marks)\n"
            f"Step 1: sapply evaluation on vec c(2, 4, 6, 8, 10) yields: c(20, 40, 36, 64, 100).\n"
            f"Step 2: Naming creates elements K1: 20, K2: 40, K3: 36, K4: 64, K5: 100.\n"
            f"Step 3: Modulo filter res %% 4 == 0 keeps all elements.\n"
            f"Console Output:\n"
            f" K1  K2  K3  K4  K5 \n"
            f" 20  40  36  64 100\n\n"
            f"### Part II: Defect Identification & Correction ({marks_b} Marks)\n"
            f"1. Bug Identification: `if (x > 5)` throws an error: 'missing value where TRUE/FALSE needed' if x is NA.\n"
            f"2. Corrected Code:\n"
            f"```R\n"
            f"safe_res <- ifelse(!is.na(vec) & vec > 5, vec^2, vec * 10)\n"
            f"```"
        )
        marking_sch = (
            f"Part I ({marks_a} Marks): Accurate step-by-step trace and exact console output.\n"
            f"Part II ({marks_b} Marks): Precise identification of NA failure and valid defensive code fix."
        )
        rubric_crit = [
            {"criterion": "Part I: Output Prediction & Trace", "marks": marks_a, "description": "Accurate output determination and execution flow trace"},
            {"criterion": "Part II: Debugging & Defensive Coding", "marks": marks_b, "description": "Root-cause bug identification and corrected defensive code"}
        ]

    # Coherent Combination 3: Assertion-Reason + Numerical / Verification
    elif (type_a in ["assertion_reason"] and type_b in ["numerical_problem"]) or \
         (type_b in ["assertion_reason"] and type_a in ["numerical_problem"]):
        stem = (
            f"Part I (Assertion Analysis - {marks_a} Marks):\n"
            f"Given the following statements regarding {topic_clean}:\n"
            f"Assertion (A): Ordinary Least Squares (OLS) estimators remain unbiased in R even if residual errors exhibit heteroscedasticity.\n"
            f"Reason (R): The Gauss-Markov theorem requires homoscedasticity only for the minimum variance (efficiency) property, not unbiasedness.\n"
            f"Determine whether both statements are true and whether Reason (R) correctly explains Assertion (A).\n\n"
            f"Part II (Numerical Verification - {marks_b} Marks):\n"
            f"Given fitted model residuals `e <- c(1.2, -0.8, 2.5, -1.4, 0.5)` with predictor `x <- c(1, 2, 3, 4, 5)`, verify through stepwise calculations in R "
            f"whether the residuals satisfy orthogonality `sum(e * x) = 0`."
        )
        model_ans = (
            f"### Part I: Assertion-Reasoning Evaluation ({marks_a} Marks)\n"
            f"Evaluation: Both (A) and (R) are TRUE, and Reason (R) is the CORRECT explanation of Assertion (A).\n"
            f"Unbiasedness requires only E(epsilon|X) = 0. Heteroscedasticity compromises standard error estimates and efficiency, not unbiasedness.\n\n"
            f"### Part II: Numerical Verification ({marks_b} Marks)\n"
            f"Product terms: e * x = c(1.2*1, -0.8*2, 2.5*3, -1.4*4, 0.5*5) = c(1.2, -1.6, 7.5, -5.6, 2.5)\n"
            f"Sum of products: 1.2 - 1.6 + 7.5 - 5.6 + 2.5 = 4.0 != 0.\n"
            f"Conclusion: The provided residual vector is not orthogonal to x, indicating unconstrained or non-converged estimates."
        )
        marking_sch = (
            f"Part I ({marks_a} Marks): Correct assessment of Assertion & Reason with theoretical backing.\n"
            f"Part II ({marks_b} Marks): Stepwise computation of product terms and orthogonality conclusion."
        )
        rubric_crit = [
            {"criterion": "Part I: Assertion-Reason Validation", "marks": marks_a, "description": "Rigorous theoretical evaluation of Gauss-Markov conditions"},
            {"criterion": "Part II: Stepwise Numerical Computation", "marks": marks_b, "description": "Accurate scalar products, summation, and interpretation"}
        ]

    # Coherent Combination 4: Case Study + System Design / Architecture
    elif (type_a in ["case_study"] and type_b in ["design_application", "architecture_diagram"]) or \
         (type_b in ["case_study"] and type_a in ["design_application", "architecture_diagram"]):
        stem = (
            f"Part I (Case Study Scenario Diagnosis - {marks_a} Marks):\n"
            f"An institutional analytics team processes real-time sensor streams using R. In {topic_clean}, the team experiences memory exhaustion "
            f"and inconsistent factor encoding during peak ingestion. Analyze this scenario, identifying 3 key operational bottlenecks.\n\n"
            f"Part II (Scalable System Architecture - {marks_b} Marks):\n"
            f"Design an end-to-end, fault-tolerant R data pipeline resolving these bottlenecks. Provide architectural component diagrams, "
            f"chunked ingestion routines, and data verification steps."
        )
        model_ans = (
            f"### Part I: Scenario Diagnostic Analysis ({marks_a} Marks)\n"
            f"1. Memory Exhaustion: Caused by in-memory data frames growing uncontrollably without garbage collection or chunked streams.\n"
            f"2. Dynamic Factor Drift: Unseen levels arriving in live batches cause integer mapping mismatches.\n"
            f"3. Single-threaded Bottleneck: Base R runs single-threaded by default on core routines.\n\n"
            f"### Part II: Scalable Pipeline Architecture ({marks_b} Marks)\n"
            f"1. Architecture Components: Ingestion Queue -> Chunk Reader (readr/data.table) -> Predefined Schema Validator -> Model Scoring -> Disk-backed HDF5 / Parquet storage.\n"
            f"2. Code Implementation with chunking and factor stabilization."
        )
        marking_sch = (
            f"Part I ({marks_a} Marks): Clear identification of 3 operational bottlenecks with root causes.\n"
            f"Part II ({marks_b} Marks): Robust architectural design, component flow, and defensive R script."
        )
        rubric_crit = [
            {"criterion": "Part I: Case Scenario Diagnosis", "marks": marks_a, "description": "In-depth identification of bottlenecks and failure modes"},
            {"criterion": "Part II: Architecture & System Design", "marks": marks_b, "description": "Modular pipeline architecture addressing memory and scalability"}
        ]

    # General Pair Fallback
    else:
        label_a = type_a.replace('_', ' ').title()
        label_b = type_b.replace('_', ' ').title()
        stem = (
            f"Part I ({label_a} - {marks_a} Marks):\n"
            f"Formulate and address the {label_a.lower()} requirements for {topic_clean} in R, detailing the core technical mechanisms.\n\n"
            f"Part II ({label_b} - {marks_b} Marks):\n"
            f"Extend your solution through {label_b.lower()}, evaluating the operational behavior, performance implications, and practical limitations in R."
        )
        model_ans = (
            f"### Part I: {label_a} Solution ({marks_a} Marks)\n"
            f"Comprehensive technical treatment of {topic_clean} covering definitions, mathematical/syntactic formulation, and base R constructs.\n\n"
            f"### Part II: {label_b} Extension ({marks_b} Marks)\n"
            f"Detailed discussion addressing practical deployment, analytical rigor, and comparison with alternatives in R."
        )
        marking_sch = (
            f"Part I ({marks_a} Marks): Structured formulation of {label_a.lower()} criteria.\n"
            f"Part II ({marks_b} Marks): Rigorous analysis under {label_b.lower()} paradigm."
        )
        rubric_crit = [
            {"criterion": f"Part I ({label_a})", "marks": marks_a, "description": f"Detailed execution under {label_a}"},
            {"criterion": f"Part II ({label_b})", "marks": marks_b, "description": f"Rigorous evaluation under {label_b}"}
        ]

    used_questions.add(stem)

    # Provenance tracking
    if supporting_chunk:
        src_file = supporting_chunk.get("source_filename", "Uploaded Lecture Notes")
        src_page = f"Slide {supporting_chunk.get('slide_or_page_number', 1)}"
        supp_text = clean_supporting_passage(supporting_chunk.get("matched_excerpt") or supporting_chunk.get("content", ""))
        conf = float(supporting_chunk.get("confidence_score", 0.88))
        gen_method = "rag_grounded"
    else:
        src_file = "Approved Institutional Syllabus"
        src_page = f"Unit {u_num}"
        supp_text = f"Syllabus Unit {u_num}: {unit.get('title', '')} - Topic: {topic_clean}"
        conf = 1.0
        gen_method = "syllabus_grounded"

    raw_q = {
        "question_text": stem,
        "marks": marks,
        "co_level": co_level,
        "bloom_level": bloom_level,
        "source_topic": topic_clean,
        "difficulty": "Hard" if marks >= 10 else "Medium",
        "unit_number": u_num,
        "source_filename": src_file,
        "source_page_or_slide": src_page,
        "supporting_passage": supp_text,
        "alignment_confidence": conf,
        "generation_method": gen_method,
        "question_type": combined_type_str,
        "options_json": None,
        "correct_answer_json": None,
        "explanation": None,
        "distractor_explanations_json": None,
        "model_answer": model_ans,
        "marking_scheme": marking_sch,
        "stepwise_solution": model_ans,
        "rubric_json": json.dumps({"criteria": rubric_crit})
    }

    # Two-Pass Validation Execution:
    co_dict = {"code": co_level, "unit_title": unit.get("title", "")}
    val_res = evaluate_semantic_quality(raw_q, unit, co_dict, existing_stems)

    raw_q["question_text"] = val_res["cleaned_text"]
    raw_q["grammar_score"] = val_res["grammar_score"]
    raw_q["quality_score"] = val_res["quality_score"]
    raw_q["status"] = val_res["status"]
    raw_q["validation_details_json"] = val_res["details_json"]
    raw_q["needs_review_reasons"] = "; ".join(val_res["reasons"]) if val_res["reasons"] else None
    raw_q["is_validated"] = False

    return raw_q

def synthesize_grounded_question(
    unit: Dict[str, Any],
    topic: str,
    bloom_level: str,
    marks: int,
    co_level: str,
    question_type: Any = "short_answer",
    mcq_config: Optional[Dict[str, Any]] = None,
    supporting_chunk: Optional[Dict[str, Any]] = None,
    used_questions: Optional[set] = None,
    existing_stems: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Synthesize an academically rigorous question strictly grounded in R Programming
    adhering to assigned question type, marks depth, Bloom action verbs, and quality rules.
    Supports single types and combined coherent question types.
    """
    if used_questions is None:
        used_questions = set()
    if existing_stems is None:
        existing_stems = []

    # Check if multiple types were passed (combined question)
    norm_types = normalize_question_types(question_type)
    if len(norm_types) > 1:
        return synthesize_combined_type_question(
            unit=unit,
            topic=topic,
            bloom_level=bloom_level,
            marks=marks,
            co_level=co_level,
            types=norm_types,
            mcq_config=mcq_config,
            supporting_chunk=supporting_chunk,
            used_questions=used_questions,
            existing_stems=existing_stems
        )

    single_type = norm_types[0] if norm_types else "short_answer"
    u_num = str(unit.get("number", "1"))
    unit_bank = R_PROGRAMMING_QUESTION_BANK.get(u_num, R_PROGRAMMING_QUESTION_BANK["1"])

    # Match requested question type in bank
    q_type_key = "mcq" if single_type in ["mcq", "multiple_select", "true_false", "matching", "fill_in_blank", "assertion_reason"] else (
        "programming" if single_type in ["programming", "debugging", "code_snippet_analysis", "output_prediction", "sql_query"] else (
            "design_application" if single_type in ["design_application", "case_study", "architecture_diagram"] or marks >= 15 else "descriptive"
        )
    )

    candidates = unit_bank.get(q_type_key, unit_bank.get("descriptive", []))
    if not candidates:
        candidates = unit_bank.get("descriptive", [])

    # Find candidate matching topic or pick first available unused
    selected = None
    for cand in candidates:
        cand_stem = cand.get("stem", "")
        if cand_stem not in used_questions and (not topic or topic.lower() in cand.get("topic", "").lower()):
            selected = cand
            break
            
    if not selected and candidates:
        for cand in candidates:
            if cand.get("stem", "") not in used_questions:
                selected = cand
                break
                
    if not selected:
        selected = random.choice(candidates) if candidates else {
            "topic": topic or unit.get("title", "R Programming"),
            "stem": f"Explain the practical implementation and statistical significance of {topic} in R with illustrative examples.",
            "bloom": bloom_level,
            "difficulty": "Medium",
            "model_answer": f"Comprehensive discussion of {topic} covering syntax, functions, and interpretation in R.",
            "marking_scheme": "Structured mark allocation based on concepts, syntax, and examples."
        }

    stem = selected.get("stem", "")
    used_questions.add(stem)

    # Resolve options and answer keys for MCQs
    options_json = None
    correct_key = None
    explanation = None
    distractor_expl_json = None

    if q_type_key == "mcq":
        raw_options = selected.get("options", [])
        correct_key = selected.get("correct", "A")
        explanation = selected.get("explanation", "")
        distractors = dict(selected.get("distractors", {}))

        # Normalize options to canonical list of dicts: [{"label": "A", "text": "...", "is_correct": bool}]
        canonical_options = []
        for idx, opt in enumerate(raw_options):
            lbl = chr(65 + idx)
            if isinstance(opt, dict):
                l = (opt.get("label") or lbl).strip().upper()
                t = str(opt.get("text", "")).strip()
                corr = opt.get("is_correct")
                if corr is None:
                    corr = (l == correct_key)
                else:
                    corr = (corr is True or corr == 1 or corr == "1" or str(corr).lower() == "true")
            else:
                opt_str = str(opt).strip()
                t = re.sub(r'^[A-E][\)\.]\s*', '', opt_str).strip()
                l = lbl
                corr = (l == correct_key)
            canonical_options.append({
                "label": l,
                "text": t,
                "is_correct": bool(corr)
            })

        # Handle MCQ Config: Options count (4 or 5)
        opts_count = (mcq_config or {}).get("options_count", 4)
        if opts_count == 5 and len(canonical_options) == 4:
            canonical_options.append({
                "label": "E",
                "text": "None of the above",
                "is_correct": False
            })
            distractors["E"] = "None of the above is not applicable for this question."

        # Handle None of the above / All of the above if configured
        if mcq_config and mcq_config.get("include_none_of_above") and len(canonical_options) == 4:
            canonical_options[3] = {
                "label": "D",
                "text": "None of the above",
                "is_correct": False
            }
            distractors["D"] = "None of the above is incorrect."

        # For single-correct MCQ, verify exactly one is_correct matches correct_key
        if question_type not in ["multiple_select", "mcq_multiple"]:
            for opt in canonical_options:
                opt["is_correct"] = (opt["label"] == correct_key)

        options_json = json.dumps(canonical_options)
        distractor_expl_json = json.dumps(distractors)

        model_ans = selected.get("model_answer")
        if not model_ans:
            model_ans = f"Correct Option: {correct_key}.\n\nExplanation: {explanation}"
        marking_sch = selected.get("marking_scheme")
        if not marking_sch:
            marking_sch = f"{marks} Marks: Selecting the correct option ({correct_key}) with technical justification."
    else:
        model_ans = selected.get("model_answer", "")
        marking_sch = selected.get("marking_scheme", "")

    # Provenance tracking
    if supporting_chunk:
        src_file = supporting_chunk.get("source_filename", "Uploaded Lecture Notes")
        src_page = f"Slide {supporting_chunk.get('slide_or_page_number', 1)}"
        supp_text = clean_supporting_passage(supporting_chunk.get("matched_excerpt") or supporting_chunk.get("content", ""))
        conf = float(supporting_chunk.get("confidence_score", 0.88))
        gen_method = "rag_grounded"
    else:
        src_file = "Approved Institutional Syllabus"
        src_page = f"Unit {u_num}"
        supp_text = f"Syllabus Unit {u_num}: {unit.get('title', '')} - Prescribed Topic: {selected.get('topic', topic)}"
        conf = 1.0
        gen_method = "syllabus_grounded"

    # Construct initial raw question dictionary
    raw_q = {
        "question_text": stem,
        "marks": marks,
        "co_level": co_level,
        "bloom_level": selected.get("bloom", bloom_level),
        "source_topic": selected.get("topic", topic),
        "difficulty": selected.get("difficulty", "Medium"),
        "unit_number": u_num,
        "source_filename": src_file,
        "source_page_or_slide": src_page,
        "supporting_passage": supp_text,
        "alignment_confidence": conf,
        "generation_method": gen_method,
        "question_type": "mcq_single" if q_type_key == "mcq" and question_type in ["mcq", "short_answer", "mcq_single"] else (
            "mcq_multiple" if question_type in ["multiple_select", "mcq_multiple"] else (
                question_type if question_type != "short_answer" else q_type_key
            )
        ),
        "options_json": options_json,
        "correct_answer_json": correct_key,
        "explanation": explanation,
        "distractor_explanations_json": distractor_expl_json,
        "model_answer": model_ans,
        "marking_scheme": marking_sch,
        "stepwise_solution": model_ans
    }

    # Two-Pass Validation Execution:
    co_dict = {"code": co_level, "unit_title": unit.get("title", "")}
    val_res = evaluate_semantic_quality(raw_q, unit, co_dict, existing_stems)

    raw_q["question_text"] = val_res["cleaned_text"]
    raw_q["grammar_score"] = val_res["grammar_score"]
    raw_q["quality_score"] = val_res["quality_score"]
    raw_q["status"] = val_res["status"]
    raw_q["validation_details_json"] = val_res["details_json"]
    raw_q["needs_review_reasons"] = "; ".join(val_res["reasons"]) if val_res["reasons"] else None
    raw_q["is_validated"] = False

    # Rubric construction
    rubric = {
        "criteria": [
            {"criterion": "Technical & Conceptual Accuracy", "marks": round(marks * 0.35, 1), "description": "Accurate concepts without statistical or syntactic errors"},
            {"criterion": "Syntax & Implementation", "marks": round(marks * 0.40, 1), "description": "Structured R expressions, function usage, and algorithmic flow"},
            {"criterion": "Interpretation & Output Verification", "marks": round(marks * 0.25, 1), "description": "Rigorous discussion of results, trade-offs, and output interpretation"}
        ]
    }
    raw_q["rubric_json"] = json.dumps(rubric)

    return raw_q

def synthesize_question(
    topic: str,
    bloom_level: str,
    marks: int,
    co_level: str,
    unit: Optional[Dict[str, Any]] = None,
    supporting_chunk: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Compatibility wrapper for question synthesis."""
    return synthesize_grounded_question(
        unit=unit or {"number": "1", "title": "Unit 1", "topics": topic},
        topic=topic,
        bloom_level=bloom_level,
        marks=marks,
        co_level=co_level,
        supporting_chunk=supporting_chunk
    )

def generate_questions_from_blueprint(
    blueprint: Dict[str, Any],
    syllabus_text: str,
    course_outcomes: List[Dict[str, Any]],
    units: List[Dict[str, Any]],
    aligned_chunks: Optional[List[Dict[str, Any]]] = None,
    generation_mode: str = "syllabus_ppt",
    gemini_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate questions following blueprint specification, syllabus units, and aligned slide chunks.
    Enforces strict Unit <-> CO mapping, authentic question types, OR-pair equivalence,
    and two-pass semantic quality validation.
    """
    if not units:
        from app.services.co_extractor import extract_syllabus_units
        units = extract_syllabus_units(syllabus_text)

    if not course_outcomes:
        from app.services.co_extractor import extract_course_outcomes
        course_outcomes = extract_course_outcomes(syllabus_text)

    # Index aligned chunks strictly by unit_number
    chunks_by_unit = {}
    if aligned_chunks:
        for a in aligned_chunks:
            if a.get("classification") in ["Strong alignment", "Review recommended"]:
                u = str(a.get("unit_number", "1"))
                chunks_by_unit.setdefault(u, []).append(a)

    sections = blueprint.get("sections", [])
    if not sections:
        sections = [
            {
                "name": "Part A",
                "instructions": "Answer ALL questions. Each carries 2 marks.",
                "questions_count": 10,
                "marks_per_question": 2,
                "has_internal_choice": False,
                "question_type": "mcq",
                "co_distribution": ["CO1", "CO1", "CO2", "CO2", "CO3", "CO3", "CO4", "CO4", "CO5", "CO5"],
                "bloom_distribution": ["L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand"]
            },
            {
                "name": "Part B",
                "instructions": "Answer either (a) OR (b) from each question. Each carries 13 marks.",
                "questions_count": 5,
                "marks_per_question": 13,
                "has_internal_choice": True,
                "question_type": "programming",
                "co_distribution": ["CO1", "CO2", "CO3", "CO4", "CO5"],
                "bloom_distribution": ["L3 - Apply", "L3 - Apply", "L3 - Apply", "L4 - Analyze", "L5 - Evaluate"]
            },
            {
                "name": "Part C",
                "instructions": "Answer the following question. Carries 15 marks.",
                "questions_count": 1,
                "marks_per_question": 15,
                "has_internal_choice": False,
                "question_type": "design_application",
                "co_distribution": ["CO5"],
                "bloom_distribution": ["L6 - Create"]
            }
        ]

    generated_questions = []
    used_questions = set()
    all_stems = []
    q_counter = 1

    for sec in sections:
        sec_name = sec.get("name", "Part A")
        q_count = sec.get("questions_count", 5)
        marks = sec.get("marks_per_question", 2)
        co_dist = sec.get("co_distribution", [])
        bloom_dist = sec.get("bloom_distribution", [])
        has_choice = sec.get("has_internal_choice", False)
        sec_raw_types = sec.get("question_types") or sec.get("question_type", "short_answer")
        sec_types = normalize_question_types(sec_raw_types)
        mcq_conf = sec.get("mcq_config", None)
        combine_types = sec.get("combine_types", False)

        questions_in_sec = sec.get("questions")
        if questions_in_sec and len(questions_in_sec) > 0:
            # Slot-by-slot generation conforming strictly to extracted blueprint template
            handled_slots = set()
            for s_idx, slot in enumerate(questions_in_sec):
                q_num = str(slot.get("question_number", q_counter))
                if q_num in handled_slots:
                    continue

                slot_marks = int(slot.get("marks") or marks)
                slot_co = slot.get("co_level") or (co_dist[s_idx % len(co_dist)] if co_dist else "CO1")
                slot_bloom = slot.get("bloom_level") or (bloom_dist[s_idx % len(bloom_dist)] if bloom_dist else "L2 - Understand")

                raw_slot_types = slot.get("question_types")
                if raw_slot_types:
                    slot_types = normalize_question_types(raw_slot_types)
                else:
                    slot_types = sec_types

                or_with = slot.get("or_pair_with")
                or_partner_slot = None
                if or_with:
                    or_partner_slot = next((s for s in questions_in_sec if str(s.get("question_number")) == str(or_with)), None)

                co_id = re.sub(r'[^0-9]', '', str(slot_co))
                target_unit_num = co_id if co_id in ["1", "2", "3", "4", "5"] else str((s_idx % 5) + 1)
                target_unit = next((u for u in units if str(u.get("number", "")) == target_unit_num), None)
                if not target_unit:
                    target_unit = units[int(target_unit_num) - 1] if len(units) >= int(target_unit_num) else {"number": target_unit_num, "title": f"Unit {target_unit_num}", "topics": ""}

                u_num = str(target_unit.get("number", target_unit_num))
                topics = parse_syllabus_topics(target_unit.get("topics", "")) or [target_unit.get("title", f"Unit {u_num}")]
                topic_a = topics[s_idx % len(topics)]

                avail_chunks = chunks_by_unit.get(u_num, [])
                matched_chunk_a = next((c for c in avail_chunks if c.get("syllabus_topic") == topic_a), None) or (avail_chunks[0] if avail_chunks else None)

                q_type_for_a = slot_types if (slot.get("combine_types") or (len(slot_types) > 1 and ("+" in str(slot.get("preferred_type", "")) or slot_marks >= 10))) else slot_types[0]

                if or_partner_slot:
                    pair_id = f"or_pair_{q_counter}"
                    q_a = synthesize_grounded_question(
                        unit=target_unit,
                        topic=topic_a,
                        bloom_level=slot_bloom,
                        marks=slot_marks,
                        co_level=slot_co,
                        question_type=q_type_for_a,
                        mcq_config=mcq_conf,
                        supporting_chunk=matched_chunk_a,
                        used_questions=used_questions,
                        existing_stems=all_stems
                    )
                    q_a["section_name"] = sec_name
                    q_a["question_number"] = q_num
                    q_a["or_pair_id"] = pair_id
                    all_stems.append(q_a["question_text"])

                    partner_num = str(or_partner_slot.get("question_number", f"{q_counter}(b) [OR]"))
                    partner_marks = int(or_partner_slot.get("marks") or slot_marks)
                    partner_co = or_partner_slot.get("co_level") or slot_co
                    partner_bloom = or_partner_slot.get("bloom_level") or slot_bloom

                    topic_b = topics[(s_idx + 1) % len(topics)]
                    matched_chunk_b = next((c for c in avail_chunks if c.get("syllabus_topic") == topic_b), None) or (avail_chunks[1] if len(avail_chunks) > 1 else (avail_chunks[0] if avail_chunks else None))

                    partner_raw_types = or_partner_slot.get("question_types")
                    partner_types = normalize_question_types(partner_raw_types) if partner_raw_types else slot_types
                    q_type_for_b = partner_types if (or_partner_slot.get("combine_types") or (len(partner_types) > 1 and ("+" in str(or_partner_slot.get("preferred_type", "")) or partner_marks >= 10))) else partner_types[0]

                    q_b = synthesize_grounded_question(
                        unit=target_unit,
                        topic=topic_b,
                        bloom_level=partner_bloom,
                        marks=partner_marks,
                        co_level=partner_co,
                        question_type=q_type_for_b,
                        mcq_config=mcq_conf,
                        supporting_chunk=matched_chunk_b,
                        used_questions=used_questions,
                        existing_stems=all_stems
                    )
                    q_b["section_name"] = sec_name
                    q_b["question_number"] = partner_num
                    q_b["or_pair_id"] = pair_id
                    all_stems.append(q_b["question_text"])

                    equiv_score, equiv_notes = evaluate_or_pair_equivalence(q_a, q_b)
                    q_a["or_equivalence_score"] = equiv_score
                    q_a["or_equivalence_notes"] = equiv_notes
                    q_b["or_equivalence_score"] = equiv_score
                    q_b["or_equivalence_notes"] = equiv_notes

                    generated_questions.append(q_a)
                    generated_questions.append(q_b)
                    handled_slots.add(q_num)
                    handled_slots.add(partner_num)
                    q_counter += 1
                else:
                    q = synthesize_grounded_question(
                        unit=target_unit,
                        topic=topic_a,
                        bloom_level=slot_bloom,
                        marks=slot_marks,
                        co_level=slot_co,
                        question_type=q_type_for_a,
                        mcq_config=mcq_conf,
                        supporting_chunk=matched_chunk_a,
                        used_questions=used_questions,
                        existing_stems=all_stems
                    )
                    q["section_name"] = sec_name
                    q["question_number"] = q_num
                    all_stems.append(q["question_text"])
                    generated_questions.append(q)
                    handled_slots.add(q_num)
                    q_counter += 1
            continue

        for i in range(q_count):
            co = co_dist[i % len(co_dist)] if co_dist else f"CO{(i % 5) + 1}"
            bloom = bloom_dist[i % len(bloom_dist)] if bloom_dist else ("L1 - Remember" if marks <= 2 else "L3 - Apply")

            # Determine question type for question i
            if combine_types or (len(sec_types) > 1 and ("+" in str(sec.get("question_type", "")) or (marks >= 10 and has_choice))):
                cur_q_type = sec_types
            else:
                cur_q_type = sec_types[i % len(sec_types)]

            # STRICT UNIT <-> CO MAPPING:
            co_id = re.sub(r'[^0-9]', '', co)
            target_unit_num = co_id if co_id in ["1", "2", "3", "4", "5"] else str((i % 5) + 1)

            target_unit = next((u for u in units if str(u.get("number", "")) == target_unit_num), None)
            if not target_unit:
                target_unit = units[int(target_unit_num) - 1] if len(units) >= int(target_unit_num) else {"number": target_unit_num, "title": f"Unit {target_unit_num}", "topics": ""}

            u_num = str(target_unit.get("number", target_unit_num))

            topics = parse_syllabus_topics(target_unit.get("topics", ""))
            if not topics:
                topics = [target_unit.get("title", f"Unit {u_num}")]

            topic_a = topics[i % len(topics)]

            avail_chunks = chunks_by_unit.get(u_num, [])
            matched_chunk_a = next((c for c in avail_chunks if c.get("syllabus_topic") == topic_a), None)
            if not matched_chunk_a and avail_chunks:
                matched_chunk_a = avail_chunks[0]

            if has_choice:
                pair_id = f"or_pair_{q_counter}"

                q_a = synthesize_grounded_question(
                    unit=target_unit,
                    topic=topic_a,
                    bloom_level=bloom,
                    marks=marks,
                    co_level=co,
                    question_type=cur_q_type,
                    mcq_config=mcq_conf,
                    supporting_chunk=matched_chunk_a,
                    used_questions=used_questions,
                    existing_stems=all_stems
                )
                q_a["section_name"] = sec_name
                q_a["question_number"] = f"{q_counter}(a)"
                q_a["or_pair_id"] = pair_id
                all_stems.append(q_a["question_text"])

                topic_b = topics[(i + 1) % len(topics)]
                matched_chunk_b = next((c for c in avail_chunks if c.get("syllabus_topic") == topic_b), None)
                if not matched_chunk_b and len(avail_chunks) > 1:
                    matched_chunk_b = avail_chunks[1]

                q_b = synthesize_grounded_question(
                    unit=target_unit,
                    topic=topic_b,
                    bloom_level=bloom,
                    marks=marks,
                    co_level=co,
                    question_type=cur_q_type,
                    mcq_config=mcq_conf,
                    supporting_chunk=matched_chunk_b,
                    used_questions=used_questions,
                    existing_stems=all_stems
                )
                q_b["section_name"] = sec_name
                q_b["question_number"] = f"{q_counter}(b) [OR]"
                q_b["or_pair_id"] = pair_id
                all_stems.append(q_b["question_text"])

                equiv_score, equiv_notes = evaluate_or_pair_equivalence(q_a, q_b)
                q_a["or_equivalence_score"] = equiv_score
                q_a["or_equivalence_notes"] = equiv_notes
                q_b["or_equivalence_score"] = equiv_score
                q_b["or_equivalence_notes"] = equiv_notes

                generated_questions.append(q_a)
                generated_questions.append(q_b)
                q_counter += 1
            else:
                q = synthesize_grounded_question(
                    unit=target_unit,
                    topic=topic_a,
                    bloom_level=bloom,
                    marks=marks,
                    co_level=co,
                    question_type=cur_q_type,
                    mcq_config=mcq_conf,
                    supporting_chunk=matched_chunk_a,
                    used_questions=used_questions,
                    existing_stems=all_stems
                )
                q["section_name"] = sec_name
                q["question_number"] = str(q_counter)
                all_stems.append(q["question_text"])
                generated_questions.append(q)
                q_counter += 1

    return generated_questions

def regenerate_single_question(
    existing_question: Dict[str, Any],
    directive: str = "standard",
    target_bloom: Optional[str] = None,
    target_difficulty: Optional[str] = None,
    target_topic: Optional[str] = None,
    target_type: Optional[str] = None,
    unit: Optional[Dict[str, Any]] = None,
    supporting_chunk: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Regenerate a single question guided by faculty feedback directives.
    Directives:
      - 'simplify_wording': Cleans language and shortens stem.
      - 'increase_difficulty': Shifts Bloom level higher and uses advanced R problem.
      - 'decrease_difficulty': Shifts Bloom level lower for fundamental syntax/recall.
      - 'convert_to_mcq': Formats as MCQ with options, distractors, and key.
      - 'make_programming': Converts to hands-on executable R code problem.
      - 'correct_grammar_only': Fixes awkward phrasing without changing concept.
    """
    q_copy = dict(existing_question)
    bloom = target_bloom or q_copy.get("bloom_level", "L2 - Understand")
    diff = target_difficulty or q_copy.get("difficulty", "Medium")
    topic = target_topic or q_copy.get("source_topic", "R Programming")
    q_type = target_type or q_copy.get("question_type", "short_answer")
    marks = q_copy.get("marks", 2)
    u_num = str(q_copy.get("unit_number", "1"))
    co = q_copy.get("co_level", f"CO{u_num}")

    if directive == "correct_grammar_only":
        cleaned_text, g_score, _ = validate_question_grammar(q_copy.get("question_text", ""))
        q_copy["question_text"] = cleaned_text
        q_copy["grammar_score"] = g_score
        return q_copy

    if directive == "increase_difficulty":
        bloom = "L4 - Analyze" if marks <= 5 else "L5 - Evaluate"
        diff = "Hard"
    elif directive == "decrease_difficulty":
        bloom = "L1 - Remember" if marks <= 2 else "L2 - Understand"
        diff = "Easy"
    elif directive == "convert_to_mcq":
        q_type = "mcq"
        marks = 2
    elif directive == "make_programming":
        q_type = "programming"
        marks = max(marks, 10)

    synth_unit = unit or {"number": u_num, "title": f"Unit {u_num}", "topics": topic}
    new_q = synthesize_grounded_question(
        unit=synth_unit,
        topic=topic,
        bloom_level=bloom,
        marks=marks,
        co_level=co,
        question_type=q_type,
        supporting_chunk=supporting_chunk
    )

    new_q["id"] = q_copy.get("id")
    new_q["question_paper_id"] = q_copy.get("question_paper_id")
    new_q["question_number"] = q_copy.get("question_number")
    new_q["section_name"] = q_copy.get("section_name")
    new_q["or_pair_id"] = q_copy.get("or_pair_id")

    return new_q
