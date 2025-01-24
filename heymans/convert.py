import re
from pathlib import Path
import logging
logger = logging.getLogger('heymans')
logging.basicConfig(level=logging.INFO, force=True)


def from_markdown_exam(exam: str | Path, quiz_id: None | int = None) -> dict:
    """
    Converts an exam text specified in Markdown to a dict in the expected 
    structure for internal use.

    Parameters
    ----------
    exam : str or Path
        The exam content as a markdown string or a Path object pointing to the
        markdown file.
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
    ValueError
        If the exam format is invalid or lacks the expected structure.
    """
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
    exam_name = re.search(r'^#\s*(.*)', exam, re.MULTILINE)
    if exam_name:
        exam_dict['name'] = exam_name.group(1)
    else:
        raise ValueError('Invalid exam format: Exam should start with a name')

    # Extract each question block
    question_blocks = re.split(r'^##\s*', exam, flags=re.MULTILINE)[1:]
    
    for block in question_blocks:
        # Split question text from answer key
        parts = re.split(r'^(?=- )', block, flags=re.MULTILINE)
        if len(parts) < 2:
            raise ValueError(
                f'Invalid exam format: Invalid question block: {block}')
        question_name_match = re.match(r"^(.*)\n", parts[0])
        question_name = question_name_match.group(1) if question_name_match else ''
        question_text = '\n'.join(parts[0].strip().split('\n')[1:]).strip()
        answer_key = [key.lstrip('-').strip() for key in parts[1:]]

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
            points = len(question['answer_key'])
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
    """
    if not isinstance(exam, dict):
        exam = from_markdown_exam(exam)
    else:
        exam = exam.copy()  # so that we don't modify the exam in-place
    # If attempts is a string, treat it like file contents of a non-existing
    # file
    if isinstance(attempts, str):
        import io
        attempts = io.StringIO(file_or_content)
    from datamatrix.io import readtxt
    results_dm = readtxt(attempts)
    for question_nr, question in enumerate(exam['questions'], start=1):
        attempts_dm = results_dm['Q Title'] == question['name']
        question['attempts'] = []
        for attempt_row in attempts_dm:
            attempt_data = {
                'username': attempt_row.Username,
                'answer': attempt_row.Answer
            }
            question['attempts'].append(attempt_data)
        logger.info(
            f'found {len(question["attempts"])} attempts for question {question_nr}')            
    return exam
