#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import consumeFromQueue
import os
import json
import unittest


def dictWithoutKey(d, keyToRemove):
    new_d = d.copy()
    new_d.pop(keyToRemove, None)
    return new_d


class TestSimplePilotLogger(unittest.TestCase):
    def test_SimplePilotLogger(self):
        uuid = "37356d94-15c6-11e6-a600-606c663dde16"
        filenameUUID = "PilotAgentUUID"
        expectedMsgs = [
            {
                u"status": u"Landed",
                u"source": u"pilot",
                u"pilotUUID": u"37356d94-15c6-11e6-a600-606c663dde16",
                u"minorStatus": u"I will send an SOS to the world!",
            }
        ]

        with open(filenameUUID, "w") as myFile:
            myFile.write(uuid)

        os.system('python PilotLogger.py "I will send an SOS to the world!"')
        recvMsgs = consumeFromQueue.consume()
        recvMsgs = [json.loads(x) for x in recvMsgs]
        # we get rid of the timestamp field
        expectedMsgs = [dictWithoutKey(x, "timestamp") for x in expectedMsgs]
        recvMsgs = [dictWithoutKey(x, "timestamp") for x in recvMsgs]
        self.assertEqual(expectedMsgs, recvMsgs)


if __name__ == "__main__":
    unittest.main()
