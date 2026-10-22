(function () {
  'use strict';

  // These helpers follow the current backend contract, including GET for import.
  // Pass { signal } to cancel read requests when a dialog closes or changes course.
  async function request(path, { method = 'GET', body, signal } = {}) {
    const response = await fetch(`/api/brightspace${path}`, {
      method,
      signal,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: 'no-store',
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || response.redirected || data === null) {
      const error = new Error(
        response.redirected ? 'Please sign in again to use Brightspace.'
          : data?.error || `Brightspace request failed (status ${response.status}).`
      );
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function id(value) {
    if (!/^\d+$/.test(String(value)) || Number(value) <= 0) {
      throw new Error('A valid Brightspace identifier is required.');
    }
    return encodeURIComponent(value);
  }

  window.brightspaceApi = Object.freeze({
    listCourses(options = {}) {
      return request('/list/courses', options);
    },
    listQuizzes(courseId, options = {}) {
      return request(`/list/courses/${id(courseId)}/quizzes`, options);
    },
    importQuiz(courseId, quizId) {
      return request(`/import/courses/${id(courseId)}/quizzes/${id(quizId)}`);
    },
    exportQuiz(courseId, quizId) {
      return request(`/export/courses/${id(courseId)}/quizzes`, {
        method: 'POST', body: { quiz_id: quizId },
      });
    },
    exportGrades(courseId, { quizId, gradeName, gradingFormula = 'ug_bss' }) {
      return request(`/export_grades/courses/${id(courseId)}`, {
        method: 'POST',
        body: { quiz_id: quizId, grade_name: gradeName, grading_formula: gradingFormula },
      });
    },
  });
})();
