from abc import ABCMeta, abstractproperty, abstractmethod
from dimagi.utils.logging import notify_exception
from pillowtop.const import CHECKPOINT_MIN_WAIT
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging


class PillowRuntimeContext(object):
    """
    Runtime context for a pillow. Gets passed around during the processing methods
    so that other functions can use it without maintaining global state on the class.
    """
    def __init__(self, changes_seen=0, do_set_checkpoint=True):
        self.changes_seen = changes_seen
        self.do_set_checkpoint = do_set_checkpoint


class PillowBase(object):
    """
    This defines the external pillowtop API. Everything else should be considered a specialization
    on top of it.
    """
    __metaclass__ = ABCMeta

    @abstractproperty
    def document_store(self):
        """
        Returns a DocumentStore instance for retreiving documents.
        """
        pass

    @abstractproperty
    def checkpoint(self):
        """
        Returns a PillowCheckpoint instance dealing with checkpoints.
        """
        pass

    @abstractmethod
    def get_change_feed(self):
        """
        Returns a ChangeFeed instance for iterating changes.
        """
        pass

    @abstractmethod
    def get_name(self):
        pass

    def get_last_checkpoint_sequence(self):
        return self.checkpoint.get_or_create().document['seq']

    def get_checkpoint(self, verify_unchanged=False):
        return self.checkpoint.get_or_create(verify_unchanged=verify_unchanged).document

    def set_checkpoint(self, change):
        self.checkpoint.update_to(change['seq'])

    def reset_checkpoint(self):
        self.checkpoint.reset()

    def run(self):
        """
        Main entry point for running pillows forever.
        """
        pillow_logging.info("Starting pillow %s" % self.__class__)
        self.process_changes(since=self.get_last_checkpoint_sequence(), forever=True)

    def process_changes(self, since, forever):
        """
        Process changes from the changes stream.
        """
        context = PillowRuntimeContext(changes_seen=0, do_set_checkpoint=True)
        try:
            for change in self.get_change_feed().iter_changes(since=since, forever=forever):
                if change:
                    try:
                        context.changes_seen += 1
                        self.processor(change, context)
                    except Exception as e:
                        notify_exception(None, u'processor error in pillow {} {}'.format(
                            self.get_name(), e,
                        ))
                        raise
                    else:
                        self.fire_change_processed_event(change, context)
                else:
                    self.checkpoint.touch(min_interval=CHECKPOINT_MIN_WAIT)
        except PillowtopCheckpointReset:
            self.process_changes(since=self.get_last_checkpoint_sequence(), forever=forever)

    @abstractmethod
    def processor(self, change, context):
        pass

    @abstractmethod
    def fire_change_processed_event(self, change, context):
        pass


class ChangeEventHandler(object):
    """
    A change-event-handler object used in constructed pillows.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def fire_change_processed(self, change, context):
        pass


class ConstructedPillow(PillowBase):
    """
    An almost-implemented Pillow that relies on being passed the various constructor
    arguments it needs.
    """

    def __init__(self, name, document_store, checkpoint, change_feed, processor,
                 change_processed_event_handler=None):
        self._name = name
        self._document_store = document_store
        self._checkpoint = checkpoint
        self._change_feed = change_feed
        self._processor = processor
        self._change_processed_event_handler = change_processed_event_handler

    def get_name(self):
        return self._name

    def document_store(self):
        return self._document_store

    @property
    def checkpoint(self):
        return self._checkpoint

    def get_change_feed(self):
        return self._change_feed

    def processor(self, change, do_set_checkpoint=True):
        self._processor.process_change(self, change, do_set_checkpoint)

    def fire_change_processed_event(self, change, context):
        if self._change_processed_event_handler is not None:
            self._change_processed_event_handler.fire_change_processed(change, context)
