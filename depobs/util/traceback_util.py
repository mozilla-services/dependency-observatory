import io
import traceback


def exc_to_str() -> str:
    """
    Writes the traceback for an exception to an IO string.
    """
    tb_file = io.StringIO()
    traceback.print_exc(file=tb_file)
    return tb_file.getvalue()
