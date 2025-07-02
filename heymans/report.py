from pathlib import Path
import json
import numpy as np
import subprocess
from scipy.stats import spearmanr
from sigmund.model import model as chatbot_model
from datamatrix import DataMatrix
import logging
from heymans import grading_formulas, prompts, quizzes, convert, config
logger = logging.getLogger('heymans')
logging.basicConfig(level=logging.INFO, force=True)


def score(quiz_data: dict | str | Path, model: str,
          dst: str | None | Path = None) -> dict:
    """Scores student answers.
    
    Parameters
    ----------
    quiz_data : dict | str | Path
        The quiz data as a dictionary, JSON string, or file path.
    model : str
        The model identifier to conduct the validation.
    dst : str | None | Path, optional
        Destination path for saving the report, by default None.
        
    Returns
    -------
    dict
        The quiz data updated with scores and feedback
    """
    quiz_data = convert.anything_to_quiz_data(quiz_data)
    quizzes.quiz_grading_task(quiz=quiz_data, model=model)
    _write_dst(quiz_data, dst)
    return quiz_data


def validate_exam(quiz_data: dict | str | Path, model: str,
                  dst: str | None | Path = None) -> str:
    """Conducts a qualitative validation of exam questions and answer keys.
    
    Parameters
    ----------
    quiz_data : dict | str | Path
        The quiz data as a dictionary, JSON string, or file path.
    model : str
        The model identifier to conduct the validation.
    dst : str | None | Path, optional
        Destination path for saving the report, by default None.
        
    Returns
    -------
    str
        The validation report as a string.
    """    
    quiz_data = convert.anything_to_quiz_data(quiz_data)
    model = chatbot_model(None, model)
    result = ''
    for i, question in enumerate(quiz_data['questions'], start=1):
        answer_key = '\n- '.join(question['answer_key'])
        prompt = prompts.EXAM_VALIDATION_PROMPT.render(
            question_text=question['text'],
            answer_key='\n- '.join(question['answer_key']))
        if config.dummy_model:
            reply = 'Awesome question'
        else:
            reply = model.predict(prompt)
        result += f'# Question {i}\n\n## Question\n\n{question["text"]}\n\n## Answer key\n\n- {answer_key}\n\n## Evaluation\n\n{reply}\n\n'
        logger.info(f'completed validation of question {i}')
    _write_dst(result, dst)
    return result
        

def analyze_difficulty_and_discrimination(
        quiz_data: dict | str | Path, dst: str | None | Path = None,
        figure: str | None | Path = None) -> DataMatrix:
    """Generates a report of the difficulty and discrimination of an exam.
    The difficulty is the mean normalized score (divided by the maximum 
    number of points). The discrimination is the RIR index, which is the
    Spearman rank-order correlation between the score on that item, and the 
    mean score on all other items.
    
    Parameters
    ----------
    quiz_data : dict | str | Path
        The quiz data as a dictionary, or as a file path, in which case it
        will be read from file.
    dst : str | None | Path, optional
        Destination file path for saving the report, by default None.
    figure : str | None | Path, optional
        Destination file path for saving the plotted figure, by default None.

    Returns
    -------
    DataMatrix
        A matrix with analysis results.
    """
    quiz_data = convert.anything_to_quiz_data(quiz_data)
    dm = DataMatrix(length=len(quiz_data['questions']))
    for j, (row, question) in enumerate(zip(dm, quiz_data['questions'])):
        max_points = len(question['answer_key'])
        scores = np.array([attempt['score']
                           for attempt in question['attempts']])
        scores_norm = scores / max_points
        # Calculate mean score for other questions
        other_scores = [
            np.array([attempt['score']
                      for attempt in qt['attempts']]) / len(qt['answer_key'])
            for qt in quiz_data['questions'] if qt != question
        ]
        mean_student_scores = np.mean(other_scores, axis=0)
        row.question = question['name']
        row.question_nr = j + 1
        row.rir = spearmanr(scores_norm, mean_student_scores).statistic
        row.m = np.mean(scores_norm)
        row.sd = np.std(scores_norm)
    _write_dst(dm, dst)
    if figure is not None:
        figure = Path(figure) if isinstance(figure, str) else figure
        from matplotlib import pyplot as plt
        plt.figure(figsize=(8, 8))
        for i, row in enumerate(dm):
            plt.text(row.m, row.rir, str(i + 1))
        plt.xlabel('Mean score (difficulty)')
        plt.ylabel('RIR (discrimination)')
        plt.savefig(figure)
        plt.clf()

    return dm


def analyze_qualitative_errors(quiz_data: dict | str | Path, model: str,
                               threshold: float = 0.5,
                               dst: str | None | Path = None) -> str:
    """
    Conducts a qualitative analysis of incorrect student responses.
    
    Parameters
    ----------
    quiz_data : dict | str | Path
        The quiz data as a dictionary, JSON string, or file path.
    model : str
        The model identifier to conduct analysis.
    threshold : float, default=0.5
        Normalized score below which a response is considered incorrect.
    dst : str | None | Path, optional
        Destination path for saving the report, by default None.
        
    Returns
    -------
    str
        The analysis report as a string.
    """
    quiz_data = convert.anything_to_quiz_data(quiz_data)
    model = chatbot_model(None, model)
    result = ''
    for i, question in enumerate(quiz_data['questions'], start=1):
        max_points = len(question['answer_key'])
        attempts = []
        # Filter incorrect responses
        for attempt in question['attempts']:
            if attempt['score'] > max_points * threshold:
                continue
            attempt.pop('username', None)
            attempts.append(attempt)
        answer_key = '\n- '.join(question['answer_key'])
        if not attempts:
            reply = 'No incorrect answers to evaluate'
        else:
            # Prepare analysis prompt
            prompt = prompts.QUALITATIVE_ERROR_ANALYSIS_PROMPT.render(
                question_text=question['text'],
                answer_key='\n- '.join(question['answer_key']),
                student_answers=json.dumps(attempts, indent=True))
            if config.dummy_model:
                reply = 'Awesome question'
            else:
                reply = model.predict(prompt)
        result += f'# Question {i}\n\n## Question\n\n{question["text"]}\n\n## Answer key\n\n- {answer_key}\n\n## Evaluation\n\n{reply}\n\n'
        logger.info(f'completed qualitative analysis of question {i}')
    _write_dst(result, dst)
    return result


def calculate_grades(quiz_data: dict | str | Path,
                     normalize_scores: bool = True,
                     grading_formula: str = 'groningen',
                     dst: str | None | Path = None,
                     figure: str | None | Path = None) -> DataMatrix:
    """Calculates student grades for an exam based on quiz data.

    Parameters:
    ----------
    quiz_data : dict | str | Path
        The source of the quiz data, which can be a dictionary already in
        memory, a a path to a file containing such data.
    normalize_scores : bool, default=True
        Whether to normalize scores to a 0-1 range for equal weighting across
        questions.
    grading_formula : str, default='groningen'
        The name of the formula to use for converting scores to grades.
    dst : str | None | Path, default=None
        Destination path for saving the grades as a text file.
    figure : str | None | Path, default=None
        Path to save a histogram of grades as an image.

    Returns:
    -------
    DataMatrix
        A DataMatrix containing student usernames, scores, and calculated
        grades.
    
    Raises:
    ------
    ValueError
        If a grading formula is not valid or if a username is missing in any
        question.
    """
    quiz_data = convert.anything_to_quiz_data(quiz_data)
    try:
        grading_fnc = getattr(grading_formulas, grading_formula)
    except AttributeError:
        raise ValueError(f'{grading_formula} is not a valid grading formula')
    questions = quiz_data['questions']
    usernames = [attempt['username'] for attempt in questions[0]['attempts']]
    dm = DataMatrix(length=len(usernames))
    dm.username = usernames
    for row, username in zip(dm, usernames):
        scores = []
        max_total_points = 0
        for question in questions:
            max_points = len(question['answer_key'])
            max_total_points += max_points
            for attempt in question['attempts']:
                if attempt['username'] != username:
                    continue
                # If the scores should be normalized, this means that they are
                # all set to a 0-1 range so that they all count equally.
                if normalize_scores:
                    scores.append(attempt['score'] / max_points)
                else:
                    scores.append(attempt['score'])
                break
            else:
                raise ValueError(f'missing username {username}')
        row.score = np.mean(scores)
        # If the scores should not be normalized, then we still divide the 
        # total number of points by the maximum number of points on the exam,
        # but the result is that different questions may be weighted 
        # differently.
        if not normalize_scores:
            row.score /= max_total_points
        row.grade = grading_fnc(row.score)
    _write_dst(dm, dst)
    if figure is not None:
        figure = Path(figure) if isinstance(figure, str) else figure
        from matplotlib import pyplot as plt
        import seaborn as sns
        sns.histplot(list(dm.grade))
        plt.xlabel('Grades')
        plt.ylabel('Frequency')
        plt.savefig(figure)
        plt.show()
    return dm


def generate_feedback(quiz_data: dict | str | Path,
                      output_folder: str | Path = None,
                      normalize_scores: bool = True,
                      grading_formula: str = 'groningen') -> dict:
    """Generates individual feedback reports for students.

    Parameters:
    ----------
    quiz_data : dict | str | Path
        The source of the quiz data, which can be a dictionary already in
        memory, a a path to a file containing such data.
    output_folder: str | None | Path, default=None
        Output folder for saving feedback reports in markdown and PDF format.
    normalize_scores : bool, default=True
        Whether to normalize scores to a 0-1 range for equal weighting across
        questions.
    grading_formula : str, default='groningen'
        The name of the formula to use for converting scores to grades.

    Returns:
    -------
    dict
        A dict with usernames as keys and feedback in MarkDown format as 
        values.
    """                          
    quiz_data = convert.anything_to_quiz_data(quiz_data)
    grade_dm = calculate_grades(quiz_data, normalize_scores=normalize_scores,
                                grading_formula=grading_formula)
    questions = quiz_data['questions']
    usernames = [attempt['username'] for attempt in questions[0]['attempts']]
    feedback = {}
    for username in usernames:
        grade = (grade_dm.username == username).grade[0]
        s = f'# Exam grade and feedback for {username}\n\nGrade: {grade:.1f}\n\n'
        for i, question in enumerate(questions, start=1):
            answer_key = '\n- '.join(question['answer_key'])
            s += f'''## Question {i}
            
{question["text"]}
Answer key:

- {answer_key}'''
            max_points = len(question['answer_key'])
            for attempt in question['attempts']:
                if attempt['username'] != username:
                    continue
                s += f'\n\nYour answer:\n\n{attempt["answer"]}\n\nFeedback:\n\n'
                for feedback_point in attempt['feedback']:
                    s += f'- {"Correct" if feedback_point["pass"] else "Incorrect"}: {feedback_point["motivation"]}\n'
                if normalize_scores:
                    s += f'\nScore: {attempt["score"] / max_points}\n\n'
                else:
                    s += f'\nScore: {attempt["score"]} of {max_points}\n\n'
                break
        feedback[username] = s
        if output_folder is not None:
            # We're escaping slashes so that pandoc doesn't interpret them as
            # control sequences
            Path(f'{output_folder}/{username}.md').write_text(
                s.replace('\\', '\\\\'))
            p = subprocess.run(
                f'pandoc "{output_folder}/{username}.md" -o "{output_folder}/{username}.pdf"',
                shell=True)
    return feedback


def check_grading_errors(quiz_data: dict | str | Path,
                         dst: str | None | Path = None) -> str | None:
    """Checks whether any errors occured during quiz grading. These are not
    errors in the sense of incorrect answers, but rather technical errors
    while grading attempts.
    
    Parameters
    ----------
    quiz_data : dict | str | Path
        The quiz data.
    dst : str | None | Path, optional
        The destination to write the errors to. If None, the errors are not
        written to a file. The default is None. If no errors occured, no
        file is created.
    
    Returns
    -------
    str | None
        The errors as a string. If no errors occurred, None is returned.
    """
    quiz_data = convert.anything_to_quiz_data(quiz_data)    
    errors = []
    for question in quiz_data.get('questions', []):
        for attempt in question.get('attempts', []):
            motivation = attempt['feedback'][0]['motivation']
            if not motivation or motivation.startswith(quizzes.ERROR_MARKER):
                errors.append(attempt)
    if not errors:
        return None
    result = ['# Errors occurred',
              f'{len(errors)} attempts were not graded. This likely due to techical issues. The error messages are included in the motivation fields below.']
    for attempt in errors:
        result.append(json.dumps(attempt, indent=True))
    result = '\n\n'.join(result)
    _write_dst(result, dst)
    return result


def _write_dst(content: str | dict | DataMatrix, dst: str | Path):
    if dst is None:
        return
    if isinstance(dst, str):
        dst = Path(dst)
    if isinstance(content, dict):
        content = json.dumps(content, indent=True)
    if isinstance(content, str):
        dst.write_text(content)
    elif isinstance(content, DataMatrix):
        from datamatrix import io
        io.writetxt(content, dst)
