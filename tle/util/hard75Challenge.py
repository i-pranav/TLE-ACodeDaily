import datetime
import random
from typing import List
import math
import time
from collections import defaultdict

import discord
from discord.ext import commands

from tle import constants
from tle.util import codeforces_api as cf
from tle.util import codeforces_common as cf_common
from tle.util import discord_common
from tle.util.db.user_db_conn import Gitgud
from tle.util import paginator
from tle.util import cache_system2
"""
NOTE : please don't use this class... it's instantiation needs more effort for now coded is added inside the codeforces module. 

"""
class Hard75Challenge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.converter = commands.MemberConverter()

    @commands.command(brief='Hard 75 challenge')
    @cf_common.user_guard(group='hard75')
    async def hard75(self,ctx,*args):
        """
        The logic behind the bot-
        -- ;hard75 letsgo
        Checks in DB if problems have already been assigned for the day 
            if yes then 
                if they have been solved then respond accordingly 
                else respond back with the same problems 
            else fetch, store (in DB) and return 2 problem (ideally from ACDLadders)
                1. same level (rounded up) 
                2. level+ 200 (rounded down)
        
        -- ;hard75 completed
        Checks if problems were assigned to the user on the same day
            if yes then 
                if they have solved the problems then
                    1. update the Hard75 DB-> update streak count properly. 
                    2. return with his streak count 
            else respond appropriately
        
        -- ;hard75 streak
            returns the streak of the current user!   

        -- ;hard75 leaderboard
            returns the leaderboard!-> which player has the longest streak! 


            Hard75 DB schema
            identifier(user)  problem1 , problem2, Streak, lastSolveDate, longesStreak
               

            
        TBD/future scope:
            1. cron job to automatically mark completed challengs
            2. add a certificate for people who complete their 75 days challenge
        """
        validSuffixes=["letsgo","completed","streak","leaderboard"]
        
        if len(args)!=1:
            await ctx.send('Use the bot properly!')
            return 
        elif args[0] not in validSuffixes:
            await ctx.send('invalid commands used!')
            return
        """
            Use individual functions for each of the above mentioned functionality so as to keep it modular
        """
        userCommand=args[0]
        if(userCommand=="letsgo"):
            await ctx.send('letsgo command would get you the problems once coded!')
        elif(userCommand=="completed"):
            await ctx.send('completed command would get you your status once coded')
        elif(userCommand=="streak"):
            await ctx.send('streak command would get you the sreak once coded!')
        elif(userCommand=="leaderboard"):
            await ctx.send('leaderboard command would get you the leaderboard once coded!')

async def setup(bot):
    await bot.add_cog(Hard75Challenge(bot))