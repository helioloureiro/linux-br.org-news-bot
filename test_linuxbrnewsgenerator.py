#! /usr/bin/env python3
import unittest
import sys
import linuxbrnewsgenerator as lxbr

sys.dont_write_bytecode = True

class TestLinuxBRNewsGenerator(unittest.TestCase):
    bot = lxbr.NewsBot("dot.config")

    def test_isTopicOfInterest(self):
        rank = self.bot.isTopicOfInterest("Smart Lasers for Bone Surgery") 
        self.assertEqual(rank, 0)
        rank = self.bot.isTopicOfInterest("Hasura V3 Engine is in alpha")
        self.assertEqual(rank, 0)
        rank = self.bot.isTopicOfInterest("He Stole Hundreds of iPhones and Looted People's Life Savings. He Told Us How")
        self.assertEqual(rank, 0)
        rank = self.bot.isTopicOfInterest("Python Testing Essentials: A Comprehensive Guide")
        self.assertEqual(rank, 1)
        rank = self.bot.isTopicOfInterest("Show HN: ClimateTriage – Impactful open source contributions")
        self.assertEqual(rank, 1)
        rank = self.bot.isTopicOfInterest("Gemini: A Family of Highly Capable Multimodal Models")
        self.assertEqual(rank, 0)
        rank = self.bot.isTopicOfInterest("Notesnook – open-source and zero knowledge private note taking app")
        self.assertEqual(rank, 1)
        rank = self.bot.isTopicOfInterest("Das Schiff Is a GitOps Based Kubernetes Cluster as a Service Platform")
        self.assertEqual(rank, 1)

if __name__ == '__main__':
    unittest.main()
