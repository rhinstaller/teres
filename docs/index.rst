.. Teres documentation master file, created by
   sphinx-quickstart on Fri Apr 15 09:40:37 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

:mod:`teres` ---  Welcome to Teres's documentation!
===================================================

.. sectionauthor:: Peter Kotvan

.. py:module:: teres
    :synopsis: Python library for reporting test results.

.. toctree::
   :maxdepth: 2

Teres is a library for reporting results from tests written in python. So far it
provides two handler classes :py:class:`teres.handlers.LoggingHandler` and
:py:class:`teres.bkr_handlers.ThinBkrHandler` for reporting to *stdout* and to
beaker_ lab controller.

Constraints
-----------

If using `teres` module in code together with `os.fork`, the `teres` module
must be used in the same process where it's imported first (main process).
This is caused by `cleanup` which is called at the end of python process and
ensures, that all logs are correctly reported. The `cleanup` however ends
tests only in the main process, enabling usage of `os.fork`.

The API
-------

The `teres` module provides a `Reporter` class that defines the API for the end
user. Internally `Reporeter` can register multiple handlers thaking care of
actual reporting.

.. py:class:: Reporter()

    This is the class that provides the API. It hase to be initialized with set
    of handlers in a similar manner as python logging interface.

    .. py:method:: add_handler(handler)

        Add handler to the reporter class.

    .. py:method:: remove_handler(handler)

        Remove specified handler from reporter.

    .. py:method:: log(result, msg[, flags=None])

        Report message with specific *result* level, *msg*. *flags* are optional
        and could depend on handlers. The result level can be one of the
        following constants :const:`ERROR`, :const:`FAIL` , :const:`PASS`,
        :const:`FILE`, :const:`INFO`, :const:`DEBUG`, :const:`NONE`.

    .. py:method:: log_error(msg[, flags=None])

        Report a message with level :const:`ERROR`.

    .. py:method:: log_fail(msg[, flags=None])

        Report a message with level :const:`FAIL`.

    .. py:method:: log_pass(msg[, flags=None])

        Report a message with level :const:`PASS`.

    .. py:method:: log_info(msg[, flags=None])

        Report a message with level :const:`INFO`.

    .. py:method:: log_debug(msg[, flags=None])

        Report a message with level :const:`DEBUG`.

    .. py:method:: send_file(logfile[, logname=None[, msg=None[, flags=None]]])

        Report a log file. The *logfile* argument can be a path to a log file
        stored on the filesystem or a file like object. In case of file like
        object is passed the read permissions are mandatory. The *logname*
        arguments provides custom log name.

    .. py:method:: test_end()

        Flush results from all handlers and clean up.

.. py:class:: Handler([result=INFO[, process_logs=True]])

    The :py:class:`Handler` is an abstract class for implementing handlers used
    by :py:class:`Reporter`.

    :param result: Set result level. Messages with lower level will be ignored.
    :param bool process_logs: Setting this to `False` log processing can be completely disabled.

    .. py:attribute:: result

        This attribute contains the default result level.

    .. py:attribute:: process_logs

        Boolean value that indicates if log files should be processed.

    .. py:method:: emit(record)

        Decides whether we are reporting a result or a file and executes the
        correct routine to process the `record`.

    .. py:method:: _emit_log(record)

        Take care of logging a message.

    .. py:method:: _emit_file(record)

        Take care of processing a log file.

    .. py:method:: close()

        Flush all pending files and messages. Clean up.

:mod:`handlers`
---------------

.. py:module:: teres.handlers

This handler class supports reporting using python logging library. Messages are
simple redirected to logging and log files are copied to destination specified
during the initialization.

.. py:class:: LoggingHandler(name, handlers[, result=teres.INFO[, dest="/tmp/"]])

    When creating an instance of this class directory called `name` is created
    at `dest` to store log files. If `dest` is set to `None`, files are only
    recorded and not copied. The `result` level is translated into python
    logging level and set as logging level.

:mod:`bkr_handlers`
-------------------

.. py:module:: teres.bkr_handlers

.. py:class:: ThinBkrHandler([result=teres.INFO[, task_log_name="testout.log"[, task_log_dir="/tmp/"[, recipe_id=None [, lab_controller_url=None[, disable_subtasks=False[, flush_delay=15[, report_overall=None]]]]]]]])

    This handler class supports reporting to the beaker_ lab controller using its
    API. This includes converting teres result levels to those of a beaker,
    reporting the results, uploading log files. :py:meth:

    List of parameters:

    :param result_level: Default report level.
    :param str task_log_name: The name of the log file to store all test results.
    :param str task_log_dir: Log directory.
    :param str recipe_id: ID of a recipe running in beaker.
    :param str lab_controller_url: URL for communitcating with beaker.
    :param bool disable_subtasks: This parameter can completely disable creation of subtasks in beaker.
    :param int flush_delay: Delay between flushing the task log.
    :param str report_overall: Create subtask result with the overall result.

    If `recipe_id` and `lab_controller_url` aren't provided constructor tries to
    get the values from environment variables as it is defined in beaker_ API
    for alternative harness_.

    To allow the user to modify results in beaker web interface one have to use
    `flags`. Flags are passed as a `dict` with keys as flags defined in the
    module and values `True`, `False`, `None` or a value specific for the flag.

    List of flags:

    - `TASK_LOG_FILE` - This is a boolean flag indicating that provided log file
      should be sent to the task. :py:meth:`teres.Reporter.send_file()`
    - `SUBTASK_RESULT` -  This flag is used to create new subtask result in beaker
      web ui. It is accepted by log methods. :py:class:`teres.Reporter`
    - `SCORE` - This is used by logging functions to set score while creating
      subtask result. Integer value is mandatory. :py:class:`teres.Reporter`
    - `SUBTASK_LOG_FILE` -  This flag accepts optional value of result url to send
      file to specific subtask result. :py:meth:`teres.Reporter.send_file()`
    - `DEFAULT_LOG_DEST` - This boolean flag indicates that all following log
      files should be stored to this subtask by default. This can be overridden
      by `TASK_LOG_FILE` and `SUBTASK_LOG_FILE` flags and the default
      destination can be changed by using this flag again.
      :py:class:`teres.Reporter`

.. py:method:: _emit_file(record)

    This method is called from :py:class:`teres.Reporter` and stores the record
    and its type in the queue. :py:meth:`teres.bkr_handlers._thread_loop`
    continuously reads from this queue and calls
    :py:meth:`teres.bkr_handlers._thread_emit_file` or
    :py:meth:`teres.bkr_handlers._thread_emit_log` depending on the record type.

.. py:method:: _emit_log(record)

    This method is called from :py:class:`teres.Reporter` and stores the record
    and its type in the queue. :py:meth:`teres.bkr_handlers._thread_loop`
    continuously reads from this queue and calls
    :py:meth:`teres.bkr_handlers._thread_emit_file` or
    :py:meth:`teres.bkr_handlers._thread_emit_log` depending on the record type.

.. py:method:: _thread_emit_file(record)

    Through the record parameter it accepts flags that can modify the
    destination of the log file sent to beaker. Without any flags the file is
    attached to the task result. This default path can be changed to any subtask
    result by using `DEFAULT_LOG_DEST` flag.

.. py:method:: _thread_emit_log(record)

    The message passed to this method is simply stored in the task log file
    which is periodically synced with beaker. 

.. py:method:: reset_log_dest()

    This method resets default log destination to task result instead of
    particular subtask result.

.. _beaker: https://beaker-project.org/
.. _harness: https://beaker-project.org/docs/alternative-harnesses/

.. Indices and tables
.. ==================
..
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

