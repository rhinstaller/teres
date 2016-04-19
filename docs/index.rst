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
provides two handler classes `LoggingHandler` and `ThinBkrHandler` for reporting
to *stdout* and to Beaker_ lab controller.


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

:mod:`handlers`
---------------

.. py:module:: teres.handlers

This handler class supports reporting using python logging library. Messages are
simple redirected to logging and log files are copied to destination specified
during the initialization.

.. py:class:: LoggingHandler(name, handlers[, result=teres.INFO[, dest="/tmp/"]])

    When creating an instance of this class directory called `name` is created
    at `dest` to store log files. The `result` level is translated into python
    logging level and set as logging level.

:mod:`bkr_handlers`
-------------------

.. py:module:: teres.bkr_handlers

.. py:class:: ThinBkrHandler([result=teres.INFO[, job_log_name="testout.log"[, job_log_dir="/tmp/"[, recipe_id=None [, lab_controller_url=None]]]]])

    This handler class supports reporting to the Beaker_ lab controller using its
    API. This includes converting teres result levels to those of a Beaker,
    reporting the results, uploading log files.

    List of parameters:

    :param result: Default report level.
    :param str job_log_name: The name of the log file to store all test results.
    :param str job_log_dir: Log directory.
    :param str recipe_id: ID of a recipe running in Beaker.
    :param str lab_controller_url: URL for communitcating with Beaker.

    If `recipe_id` and `lab_controller_url` aren't provided constructor tries to
    get the values from environment variables as it is defined in Beaker_ API
    for alternative harness_.

    To allow user to modify results in beaker web interface one have to use
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

    This method is called from :py:class:`teres.Reporter`. Through the record
    parameter it accepts flags that can modify the destination of the log file
    sent to Beaker. Without any flags the file is attached to the task result.
    This default path can be changed to any subtask result by using
    `DEFAULT_LOG_DEST` flag.

.. py:method::reset_log_dest()

    This method resets default log destination to task result instead of
    particular subtask result.

.. _Beaker: https://beaker-project.org/
.. _harness: https://beaker-project.org/docs/alternative-harnesses/

.. Indices and tables
.. ==================
..
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

