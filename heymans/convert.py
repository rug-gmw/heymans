import re
import copy
import json
import string
from pathlib import Path
import tempfile
import logging
from . import quizzes
from .errors import AttemptsFileError, QuizFileError
logger = logging.getLogger('heymans')
logging.basicConfig(level=logging.INFO, force=True)


def _context_snippet(text: str, max_length: int = 800) -> str:
    """
    Show a text snippet to the user for parsing errors. But strip these to 800chars max, with '...' at the end.
    """
    text = text.strip()
    if len(text) <= max_length:
        return text
    return f'{text[:max_length].rstrip()}...'


def from_markdown_exam(exam: str | Path, quiz_id: None | int = None) -> dict:
    """
    Converts an exam text specified in Markdown to a dict in the expected 
    structure for internal use.

    Parameters
    ----------
    exam : str or Path
        The exam content as a markdown string or a Path object pointing to the
        markdown file. If exam is a str that corresponds to the path of an
        existing file, it is interpreted as a path, otherwise it is interpreted
        as file content.
    quiz_id : int or None, optional
        Unique quiz identifier. A random number will be generated if None is
        provided.

    Returns
    -------
    dict
        A dictionary containing the structured exam data, including the name,
        quiz_id, and questions.

    Raises
    ------
    QuizFileError
        If the exam format is invalid or lacks the expected structure. The
        exception may include a question name, context snippet, and hint for
        displaying user-facing parse errors.
    """
    if isinstance(exam, str) and '\n' not in exam and Path(exam).exists():
        exam = Path(exam)
    if isinstance(exam, Path):
        exam = exam.read_text()
    if quiz_id is None:
        import uuid
        quiz_id = uuid.uuid4().int
    # Define a dictionary to store the parsed data
    exam_dict = {
        'name': '',
        'quiz_id': quiz_id,
        'questions': []
    }
    
    # Extract the exam name
    exam_name = re.search(r'^#(?!#)\s+(.*)', exam, re.MULTILINE)
    if exam_name:
        exam_dict['name'] = exam_name.group(1)
    else:
        raise QuizFileError(
            'Quiz file should start with a "# Quiz name" heading.',
            hint='Add such a heading at the top of your file.'
        )

    # Extract each question block
    question_blocks = re.split(r'^##\s*', exam, flags=re.MULTILINE)[1:]
    
    for block in question_blocks:
        # Split question text from answer key
        parts = re.split(r'^(?=- )', block, flags=re.MULTILINE)
        question_name_match = re.match(r"^(.*)\n", parts[0])
        question_name = question_name_match.group(1) if question_name_match else ''
        # If we only have one part, then the answer key is likely missing or not formatted correctly:
        if len(parts) < 2:
            if re.search(r'^[\u2013\u2014\u2212]\s+', block, flags=re.MULTILINE):
                raise QuizFileError(
                    'Answer key points appear to use en dashes or other lookalike dash characters instead of hyphens.',
                    question_name=question_name or '(Unnamed question)',
                    context=_context_snippet(block),
                    hint='Make sure to use regular hyphens in your answer key: "-".'
                )
            raise QuizFileError(
                'This question does not contain a valid answer key.',
                question_name=question_name or '(Unnamed question)',
                context=_context_snippet(block),
                hint='Add one or more answer key lines starting with "-".'
            )
        # Allow questions to be marked for exclusion
        if '[exclude]' in question_name.lower():
            logger.info(f'excluding question: {question_name}')
            continue
        question_text = '\n'.join(parts[0].strip().split('\n')[1:]).strip()
        # Catch answer keys that do not correspond to a simple list
        if any(not part.startswith('-') or '\n' in part .strip()
               for part in parts[1:] if part.strip()):
            raise QuizFileError(
                'Answer key points should each start with "-".',
                question_name=question_name or '(Unnamed question)',
                context=_context_snippet(block),
                hint='Make sure all answer key points, and only answer key points, start with "-".'
            )
        answer_key = [key.lstrip('-').strip() for key in parts[1:]]
        # Fall back to using name as text for questions without actual text
        if not question_text.strip():
            logger.warning(f'No question text for question {question_name[:20]} (...). Using name instead.')
            question_text = question_name
        # Append to questions list
        exam_dict['questions'].append({
            'name': question_name.strip(),
            'text': question_text.strip(),
            'answer_key': answer_key
        })
    logger.info(
        f'parsed exam {exam_dict["name"]} with {len(exam_dict["questions"])} questions')
    return exam_dict


def to_brightspace_exam(exam: dict | str | Path,
                        points_per_question: None | int = 1,
                        dst: None | Path | str = None) -> str:
    """
    Converts an exam to the CSV format required by Brightspace for uploading
    questions to a quiz.

    Parameters
    ----------
    exam : dict, str, or Path
        The exam content as a dictionary, markdown string, or Path object
        pointing to the markdown file.
    points_per_question : int or None, optional
        The number of points to assign to each question. If None, the number of
        answer key elements sets the points.
    dst : Path, str, or None, optional
        If provided, specifies the destination file path for writing the CSV
        formatted exam.

    Returns
    -------
    str
        The exam formatted as a CSV string suitable for uploading to
        Brightspace.
    """
    if not isinstance(exam, dict):
        exam = from_markdown_exam(exam)
    formatted_questions = []
    for question_nr, question in enumerate(exam['questions'], start=1):
        if points_per_question is None:
            points = quizzes.answer_key_length(question['answer_key'])
        else:
            points = points_per_question

        # Function to escape double quotes
        def fix_text(text: str | list) -> str:
            if isinstance(text, list):
                text = '- ' + '<br>- '.join(text)
            return text.replace('"', '""').replace('\n', '<br>')

        # Format the question with escaped texts
        formatted_question = (
            f"NewQuestion,WR,HTML,,\n"
            f"ID,{exam['name']}-{question_nr},HTML,,\n"
            f"Title,\"{fix_text(question['name'])}\",HTML,,\n"
            f"QuestionText,\"{fix_text(question['text'])}\",HTML,,\n"
            f"Points,{points},,,\n"
            f"AnswerKey,\"{fix_text(question['answer_key'])}\",HTML,,\n"
            f"Feedback,\"{fix_text(question['answer_key'])}\",HTML,,"
        )
        formatted_questions.append(formatted_question)
    brightspace_exam = '\n'.join(formatted_questions)
    if dst is not None:
        if isinstance(dst, str):
            dst = Path(dst)
        dst.write_text(brightspace_exam)
    return brightspace_exam


def merge_brightspace_attempts(exam: dict | str | Path, attempts: str | Path,
                               dst: None | Path | str = None) -> dict:
    """
    Merges an exam with student attempts as downloaded from Brightspace.
    Brightspace question titles are matched against quiz question names. Rows
    with empty question titles fall back to matching Brightspace question text
    against quiz question text. Matching is case-insensitive and ignores double
    quotes and whitespace.

    Parameters
    ----------
    exam : dict, str, or Path
        The exam data as a dictionary, markdown string, or Path object pointing
        to the markdown file.
    attempts : str or Path
        The student attempts as a string from a CSV or Path object pointing to
        the CSV file.
    dst : Path, str, or None, optional
        If provided, specifies the destination file path for writing the merged
        results.

    Returns
    -------
    dict
        A dictionary of the exam with merged student attempts, enriching
        questions with attempt data.

    Raises
    ------
    AttemptsFileError
        If the attempts file does not contain the required Brightspace columns
        or cannot be matched to the quiz questions.
    """
    from datamatrix.io import readtxt
    
    if not isinstance(exam, dict):
        exam = from_markdown_exam(exam)
    else:
        exam = exam.copy()  # so that we don't modify the exam in-place
    attempts = _as_path(attempts)
    results_dm = readtxt(attempts)    
    columns = set(results_dm.column_names)
    missing_columns = [
        column for column in ('Answer', 'Username')
        if column not in columns
    ]
    if 'Q Title' not in columns and 'Q Text' not in columns:
        missing_columns.append('Q Title or Q Text')
    if missing_columns:
        raise AttemptsFileError(
            'The attempts file is missing required Brightspace columns.',
            context=f'Missing columns: {", ".join(missing_columns)}',
            hint='Upload the open-question attempts export from Brightspace. It should include "Answer", "Username", and either "Q Title" or "Q Text".'
        )

    total_attempts = 0
    for question_nr, question in enumerate(exam['questions'], start=1):        
        def sanitize(s):
            # Remove all whitespace and double quotes from string and convert to
            # ascii
            s = str(s)
            for ch in string.whitespace + '"':
                s = s.replace(ch, '')
            return s.lower().encode('ascii', 'ignore')
        def match_name(s):
            """A basic function to do ascii matching to avoid character-encoding
            mismatches.
            """
            return sanitize(s) == question_name
        def match_text(s):
            return sanitize(s) == question_text
        question_name = sanitize(question['name'])
        question_text = sanitize(question['text'])
        attempts_dm = []
        for attempt_row in results_dm:
            q_title = attempt_row['Q Title'] if 'Q Title' in columns else ''
            q_title_is_empty = not sanitize(q_title)
            if not q_title_is_empty and match_name(q_title):
                attempts_dm.append(attempt_row)
                continue
            if q_title_is_empty and 'Q Text' in columns and match_text(attempt_row['Q Text']):
                attempts_dm.append(attempt_row)
        if not attempts_dm:
            logger.warning(f'No attempts found for question {question_nr}')
        question['attempts'] = []
        for attempt_row in attempts_dm:
            attempt_data = {
                'username': attempt_row.Username,
                'answer': attempt_row.Answer
            }
            question['attempts'].append(attempt_data)
        total_attempts += len(question['attempts'])
        logger.info(
            f'found {len(question["attempts"])} attempts for question {question_nr}')
    if total_attempts == 0:
        raise AttemptsFileError(
            'Could not match attempts-file to quiz questions.',
            hint='Make sure your Brightspace attempts-file etiher has a "Q Title" column that matches question names, and/or a "Q Text" column that matches the question text.'
        )
    return exam


def anything_to_quiz_data(anything: dict | str | Path) -> dict:
    """Flexibly converts different sources to a quiz-data dictionary.
    
    Parameters
    ----------
    anything
        Can be a dict, path to a markdown or json file, or a string of json
        content.
        
    Returns
    -------
    dict
    """
    if isinstance(anything, dict):
        return copy.deepcopy(anything)
    if isinstance(anything, str):
        anything = Path(anything)
    if anything.exists():
        content = anything.read_text()
    else:
        content = anything
    if anything.suffix.lower() == '.md':
        return from_markdown_exam(content)
    return json.loads(content)


def _as_path(src: str | Path) -> Path:
    if isinstance(src, str):
        if '\n' not in src and Path(src).is_file():
            return Path(src)
        else:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(src.encode())
                return Path(f.name)
    elif isinstance(src, Path):
        return src
    raise TypeError("src must be a string or a Path object")
