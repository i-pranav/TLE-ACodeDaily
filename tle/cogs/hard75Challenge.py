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
from tle.util import table
"""
NOTE : please don't use this class... it's instantiation needs more effort for now coded is added inside the codeforces module. 

"""

class Hard75CogError(commands.CommandError):
    pass

class Hard75Challenge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.converter = commands.MemberConverter()

    @commands.group(brief='Hard 75 challenge',
                    invoke_without_command=True)
    @cf_common.user_guard(group='hard75')
    async def hard75(self,ctx,*args):
        """
        Hard75 is a challenge mode. The goal is to solve 2 codeforces problems every day for 75 days.
        You can request your daily problems by using ;hard75 letsgo
        If you manage to solve both problem till midnight (UTC) your current streak increases. If you don't solve both problems or miss a single day your streak will reset back to 0.
        The bot will keep track of your streak (current and longest) and there is also a leaderboard for the top contestants.
        """
        await ctx.send_help(ctx.command)

    @hard75.command(brief='Mark hard75 problems for today as completed')
    @cf_common.user_guard(group='hard75')
    async def completed(self, ctx):
        """
        Use this command once you have completed both of your daily problems
        """        
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user_id = ctx.message.author.id
        active = cf_common.user_db.check_Hard75Challenge(user_id)
        if not active:
            raise Hard75CogError(f'You have not been assigned any problems today! use `;hard75 letsgo` to get the pair of problems!')
        
        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions if sub.verdict == 'OK'}
        c1_id,p1_id,p1_name,c2_id,p2_id,p2_name=cf_common.user_db.get_Hard75Challenge(user_id)

        #commenting below for testing purposes!

        if not p1_name in solved and not p2_name in solved:
            raise Hard75CogError('You haven\'t completed either of the problems!.')
        if not p1_name in solved:
            raise Hard75CogError('You haven\'t completed the problem1!!.')
        if not p2_name in solved:
            raise Hard75CogError('You haven\'t completed the problem2!!.')
        # else I need to update accordingly... 
        today=datetime.datetime.utcnow().strftime('%Y-%m-%d')
        assigned_date,last_update=cf_common.user_db.get_Hard75Date(user_id)
        if(last_update==today):
            await ctx.send(f"Your progress has already been updated for `{today}`")
            return
        if(assigned_date!=today):
            await ctx.send(f"OOPS! you didn't solve the problems in the 24H window! you were required to solve it on `{assigned_date}`")
        # else the user has completed his task on the given day hence let's update it
        
        current_streak, longest_streak=cf_common.user_db.get_Hard75UserStat(user_id)

        yesterday=datetime.datetime.utcnow()-datetime.timedelta(days=1)
        yesterday=yesterday.strftime('%Y-%m-%d')

        #check if streak continues!
        if(last_update==yesterday):
            current_streak+=1

        if(current_streak==0):      # on first day!
            current_streak=1    

        longest_streak=max(current_streak,longest_streak)
        rc=cf_common.user_db.updateStreak_Hard75Challenge(user_id,current_streak,longest_streak)
        if(rc!=1):
            raise Hard75CogError('Some issue while monitoring progress! Please contact the ACD Team!.')
        embed = discord.Embed(description="Congratulations!!")
        embed.add_field(name='current streak', value=(current_streak))
        embed.add_field(name='longest streak', value=(longest_streak))
        
        # mention an embed which includes the streak d  ay of the user! 
        await ctx.send(f'Hi `{handle}`! You have completed your daily challenge for {today} ', embed=embed)

    
    async def _postProblemEmbed(self, ctx, handle, problem,idx):
        title = f'{problem.index}. {problem.name}'
        desc = cf_common.cache2.contest_cache.get_contest(problem.contestId).name
        embed = discord.Embed(title=title, url=problem.url, description=desc)
        embed.add_field(name='Rating', value=problem.rating)
        await ctx.send(f'Hard75 problem`#{idx}` for `{handle}` [`{datetime.datetime.utcnow().strftime("%Y-%m-%d")}`]', embed=embed)

    async def _repostProblems(self, ctx, handle,contest_id1,idx1,contest_id2,idx2):
        user_id = ctx.author.id
        issue_time = datetime.datetime.now().timestamp()
        now = datetime.datetime.now()
        start_time, end_time = cf_common.get_start_and_end_of_day(now)
        now_time = int(now.timestamp())
        url1 = f'{cf.CONTEST_BASE_URL}{contest_id1}/problem/{idx1}'
        url2 = f'{cf.CONTEST_BASE_URL}{contest_id2}/problem/{idx2}'
        embed = discord.Embed(description="Get your daily task done!")
        embed.add_field(name='Problem 1', value=(url1))
        embed.add_field(name='Problem 2', value=(url2))
        
        # mention an embed which includes the streak day of the user! 
        await ctx.send(f'You have already been assigned the problems for [`{datetime.datetime.utcnow().strftime("%Y-%m-%d")}`] `{handle}` ', embed=embed)
    
    
    @hard75.command(brief='Get Hard75 leaderboard')
    @cf_common.user_guard(group='hard75')    
    async def leaderboard(self,ctx):
        """
        Ranklist of the top contestants (based on longest streak)
        """
        data = [(ctx.guild.get_member(int(user_id)), longest_streak, current_streak)
                 for user_id, longest_streak, current_streak in cf_common.user_db.get_hard75_LeaderBoard()]
        data = [(member, longest_streak, current_streak)
                 for member, longest_streak, current_streak in data
                 if member is not None]
        if not data: 
            raise Hard75CogError('No One has completed anything as of now - leaderboard is empty!')

        _PER_PAGE = 10

        def make_page(chunk, page_num):
            style = table.Style('{:>}  {:<}  {:>}  {:>}')
            t = table.Table(style)
            t += table.Header('#', 'Name', 'Longest streak', 'Current Streak')
            t += table.Line()
            for index, (member, longestStreak, currentStreak) in enumerate(chunk):
                lstreakstr = f'{longestStreak}' 
                cstreakstr = f'{currentStreak}' 
                memberstr  = f'{member.display_name}'
                t += table.Data(_PER_PAGE * page_num + index + 1,
                                memberstr, lstreakstr, cstreakstr)

            table_str = f'```\n{t}\n```'
            embed = discord_common.cf_color_embed(description = table_str)
            return 'Leaderboard', embed

        pages = [make_page(chunk, k) for k, chunk in enumerate(
            paginator.chunkify(data, _PER_PAGE))]
        paginator.paginate(self.bot, ctx.channel, pages,
                           wait_time=5 * 60, set_pagenum_footers=True)        

        
    @hard75.command(brief='Get users streak statistics')
    @cf_common.user_guard(group='hard75')
    async def streak(self,ctx):
        """
        See your progress on the challenge 
        """        
        user_id=ctx.author.id
        res=cf_common.user_db.get_hard75_status(user_id)
        if res is None:
            raise Hard75CogError('There is no record of yours in the DB have you ever completed a Hard75 problem?')
        current_streak,longest_streak,last_updated=res
        
        embed = discord.Embed(title="Your Hard75 grind!",description="This is what you achieved!")
        embed.add_field(name='current streak', value=current_streak)
        embed.add_field(name='longest streak', value=longest_streak)
        embed.add_field(name='last problem solved on', value=last_updated)
        await ctx.send(f'Thanks for participating in the challenge!', embed=embed)

    @hard75.command(brief='Request hard75 problems for today')
    @cf_common.user_guard(group='hard75')
    async def letsgo(self,ctx):
        """
        Assigns 2 problems per day (would be fetched from ACDLadders later)
                1. same level*
                2. level+ 200*
                *-> both of them are rounded to the nearest 100
        """        
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user = cf_common.user_db.fetch_cf_user(handle)
        user_id = ctx.author.id
        activeChallenge= cf_common.user_db.check_Hard75Challenge(user_id)
        if activeChallenge:     # problems are already there simply return from the DB 
            c1_id,p1_id,p1_name,c2_id,p2_id,p2_name=cf_common.user_db.get_Hard75Challenge(user_id)

            #check if problem is already solved... if so respond appropriately.
            submissions = await cf.user.status(handle=handle)
            solved = {sub.problem.name for sub in submissions if sub.verdict == 'OK'}
            if p1_name in solved and p2_name in solved:
                dt = datetime.datetime.now()
                timeLeft=((24 - dt.hour - 1) * 60 * 60) + ((60 - dt.minute - 1) * 60) + (60 - dt.second)
                h=int(timeLeft/3600)
                m=int((timeLeft-h*3600)/60)
                embed = discord.Embed(title="Life isn't just about coding!",description=f"You need to wait {handle}!")
                embed.add_field(name='Time Remaining for next challenge', value=f"{h} Hours : {m} Mins")
                await ctx.send(f'You have already completed todays challenge! Life isn\'t just about coding!! Go home, talk to family and friends, touch grass, hit the gym!', embed=embed)
                return
            #else return that problems have already been assigned.
            await self._repostProblems(ctx,handle,c1_id,p1_id,c2_id,p2_id)
            return
        rating = round(user.effective_rating, -2)
        rating = max(800, rating)
        rating = min(3000, rating)
        rating1 = rating            # this is the rating for the problem 1
        rating2 = rating1+200       # this is the rating for the problem 2
        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions}
        problems1 = [prob for prob in cf_common.cache2.problem_cache.problems
                    if (prob.rating == rating1 
                    and prob.name not in solved)]
        problems2 = [prob for prob in cf_common.cache2.problem_cache.problems
                    if (prob.rating == rating2 
                    and prob.name not in solved)]

        def check(problem):     # check that the user isn't the author and it's not a nonstanard problem    
            return (not cf_common.is_nonstandard_problem(problem) and
                    not cf_common.is_contest_writer(problem.contestId, handle))
        problems1 = list(filter(check, problems1))
        problems2 = list(filter(check,problems2))
        if not problems1 or not problems2:
            raise Hard75CogError('Great! You have finished all the problems, do atcoder now lol!')
        
        problems1.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(problem.contestId).startTimeSeconds)
        problems2.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(problem.contestId).startTimeSeconds)
        choice1 = max(random.randrange(len(problems1)) for _ in range(5))
        choice2 = max(random.randrange(len(problems2)) for _ in range(5))
        problem1=problems1[choice1]
        problem2=problems2[choice2]
        res=cf_common.user_db.new_Hard75Challenge(user_id,handle,problem1.index,problem1.contestId,problem1.name,problem2.index,problem2.contestId,problem2.name,user.effective_rating)
        if res!=1:
            raise Hard75CogError("Issues while writing to db please contact ACD team!")
        await self._postProblemEmbed(ctx, handle, problem1,1)
        await self._postProblemEmbed(ctx, handle, problem2,2)


    @discord_common.send_error_if(Hard75CogError, cf_common.ResolveHandleError,
                                  cf_common.FilterError)
    async def cog_command_error(self, ctx, error):
        pass


async def setup(bot):
    await bot.add_cog(Hard75Challenge(bot))