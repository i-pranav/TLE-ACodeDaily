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


_GITGUD_NO_SKIP_TIME = 2 * 60 * 60
_GITGUD_SCORE_DISTRIB = (1, 2, 3, 5, 8, 12, 17, 23)
_GITGUD_SCORE_DISTRIB_MIN = -400
_GITGUD_SCORE_DISTRIB_MAX =  300
_ONE_WEEK_DURATION = 7 * 24 * 60 * 60
_GITGUD_MORE_POINTS_START_TIME = 1680300000

def _calculateGitgudScoreForDelta(delta):
    if (delta <= _GITGUD_SCORE_DISTRIB_MIN):
        return _GITGUD_SCORE_DISTRIB[0]
    if (delta >= _GITGUD_SCORE_DISTRIB_MAX):
        return _GITGUD_SCORE_DISTRIB[-1]
    index = (delta - _GITGUD_SCORE_DISTRIB_MIN)//100
    return _GITGUD_SCORE_DISTRIB[index]

class CodeforcesCogError(commands.CommandError):
    pass


class Codeforces(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.converter = commands.MemberConverter()

    # more points seasons start at April 1st 2023 (timestamp: 1680300000) and is only active in the last 7 days of the month

    # @@@ add issue and finish time constraint (both times need to be within the more points range)
    def _check_more_points_active(self, now_time, start_time, end_time):
        morePointsActive = False
        morePointsTime = end_time - _ONE_WEEK_DURATION
        if start_time >= _GITGUD_MORE_POINTS_START_TIME and now_time >= morePointsTime: 
            morePointsActive = True
        return morePointsActive

    async def _hard75_completed(self, ctx):
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user_id = ctx.message.author.id
        active = cf_common.user_db.check_Hard75Challenge(user_id)
        if not active:
            raise CodeforcesCogError(f'You have not been assigned any problems today! use `;hard75 letsgo` to get the pair of problems!')
        
        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions if sub.verdict == 'OK'}
        c1_id,p1_id,p1_name,c2_id,p2_id,p2_name=cf_common.user_db.get_Hard75Challenge(user_id)

        #commenting below for testing purposes!

        if not p1_name in solved and not p2_name in solved:
            raise CodeforcesCogError('You haven\'t completed either of the problems!.')
        if not p1_name in solved:
            raise CodeforcesCogError('You haven\'t completed the problem1!!.')
        if not p2_name in solved:
            raise CodeforcesCogError('You haven\'t completed the problem2!!.')
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
            raise CodeforcesCogError('Some issue while monitoring progress! Please contact the ACD Team!.')
        embed = discord.Embed(description="Congratulations!!")
        embed.add_field(name='current streak', value=(current_streak))
        embed.add_field(name='longest streak', value=(longest_streak))
        
        # mention an embed which includes the streak d  ay of the user! 
        await ctx.send(f'Hi `{handle}`! You have completed your daily challenge for {today} ', embed=embed)

    
    async def _hard75_Retried(self, ctx, handle,contest_id1,idx1,contest_id2,idx2):
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
    
    
    
    async def _Hard75_Leaderboard(self,ctx):
        embed = discord.Embed(title="Your Hard75 grind!",description="This is what you achieved!")
        res=cf_common.user_db.get_hard75_LeaderBoard()
        if res is None: 
            raise CodeforcesCogError('No One has completed anything as of now - leaderboard is empty!')
        names=[]
        for r in res:
            if(r=="0"):
                pass
            if((r)<1000):
                pass
            names.append(f"<@!{r}>")
        rankArr=[0]*len(names)
        for i in range(0,5):
            rankArr[i]=i+1
                
        embed=discord.Embed(
        title="Leaderboard",
        color=discord.Color.blue()
        )
        embed.add_field(name='Name',value=names,inline="true")
        embed.add_field(name='Rank',value=rankArr,inline="true")
        await ctx.send(embed=embed)

    async def _Hard75_streak(self,ctx):
        user_id=ctx.author.id
        res=cf_common.user_db.get_hard75_status(user_id)
        if res is None:
            raise CodeforcesCogError('There is no record of yours in the DB have you ever completed a Hard75 problem?')
        current_streak,longest_streak,last_updated=res
        
        embed = discord.Embed(title="Your Hard75 grind!",description="This is what you achieved!")
        embed.add_field(name='current streak', value=current_streak)
        embed.add_field(name='longest streak', value=longest_streak)
        embed.add_field(name='last problem solved on', value=last_updated)
        await ctx.send(f'Thanks for participating in the challenge!', embed=embed)


    async def _Hard75_letsgo(self,ctx,handle,user):
        user_id = ctx.author.id
        activeChallenge= cf_common.user_db.check_Hard75Challenge(user_id)
        if activeChallenge:     # problems are already there simply return from the DB 
            c1_id,p1_id,p1_name,c2_id,p2_id,p2_name=cf_common.user_db.get_Hard75Challenge(user_id)
            await self._hard75_Retried(ctx,handle,c1_id,p1_id,c2_id,p2_id)
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
            raise CodeforcesCogError('Great! You have finished all the problems, do atcoder now lol!')
        
        problems1.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(problem.contestId).startTimeSeconds)
        problems2.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(problem.contestId).startTimeSeconds)
        choice1 = max(random.randrange(len(problems1)) for _ in range(5))
        choice2 = max(random.randrange(len(problems2)) for _ in range(5))
        problem1=problems1[choice1]
        problem2=problems2[choice2]
        res=cf_common.user_db.new_Hard75Challenge(user_id,handle,problem1.index,problem1.contestId,problem1.name,problem2.index,problem2.contestId,problem2.name)
        if res!=1:
            raise CodeforcesCogError("Issues while writing to db please contact ACD team!")
        await self._hard75(ctx, handle, problem1,1)
        await self._hard75(ctx, handle, problem2,2)



    async def _hard75(self, ctx, handle, problem,idx):
        user_id = ctx.author.id
        issue_time = datetime.datetime.now().timestamp()
        #the below code updates it in the DB
        now = datetime.datetime.now()
        start_time, end_time = cf_common.get_start_and_end_of_day(now)
        now_time = int(now.timestamp())

        title = f'{problem.index}. {problem.name}'
        desc = cf_common.cache2.contest_cache.get_contest(problem.contestId).name
        embed = discord.Embed(title=title, url=problem.url, description=desc)
        embed.add_field(name='Rating', value=problem.rating)
        await ctx.send(f'Hard75 problem`#{idx}` for `{handle}` [`{datetime.datetime.utcnow().strftime("%Y-%m-%d")}`]', embed=embed)


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
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user = cf_common.user_db.fetch_cf_user(handle)
        userCommand=args[0]
        if(userCommand=="letsgo"):
            await self._Hard75_letsgo(ctx,handle,user)
            
        elif(userCommand=="completed"):
            await self._hard75_completed(ctx)

        elif(userCommand=="streak"):
            await self._Hard75_streak(ctx)
            # the logic would require implementing the database first!
            # await ctx.send('streak command would get you the sreak once coded!')

        elif(userCommand=="leaderboard"):
            await self._Hard75_Leaderboard(ctx)
            # the logic would require implementing the database first!
            # await ctx.send('leaderboard command would get you the leaderboard once coded!')


    async def _validate_gitgud_status(self, ctx, delta):
        if delta is not None and delta % 100 != 0:
            raise CodeforcesCogError('Delta must be a multiple of 100.')

        user_id = ctx.message.author.id
        active = cf_common.user_db.check_challenge(user_id)
        if active is not None:
            _, _, name, contest_id, index, _ = active
            url = f'{cf.CONTEST_BASE_URL}{contest_id}/problem/{index}'
            raise CodeforcesCogError(f'You have an active challenge {name} at {url}')

    async def _gitgud(self, ctx, handle, problem, delta):
        # The caller of this function is responsible for calling `_validate_gitgud_status` first.
        user_id = ctx.author.id

        issue_time = datetime.datetime.now().timestamp()
        rc = cf_common.user_db.new_challenge(user_id, issue_time, problem, delta)
        if rc != 1:
            raise CodeforcesCogError('Your challenge has already been added to the database!')

        # Calculate time range of given month (d=) or current month
        now = datetime.datetime.now()
        start_time, end_time = cf_common.get_start_and_end_of_month(now)
        now_time = int(now.timestamp())
        # more points seasons start at April 1st 2023 (timestamp: 1680300000) and is only active in the last 7 days of the month
        morePointsActive = self._check_more_points_active(now_time, start_time, end_time)

        points = _calculateGitgudScoreForDelta(delta)
        monthlypoints = 2 * points if morePointsActive else points

        title = f'{problem.index}. {problem.name}'
        desc = cf_common.cache2.contest_cache.get_contest(problem.contestId).name
        embed = discord.Embed(title=title, url=problem.url, description=desc)
        embed.add_field(name='Rating', value=problem.rating)
        embed.add_field(name='Alltime points', value=(points))
        embed.add_field(name='Monthly points', value=(monthlypoints))
        await ctx.send(f'Challenge problem for `{handle}`', embed=embed)

    @commands.command(brief='Upsolve a problem')
    @cf_common.user_guard(group='gitgud')
    async def upsolve(self, ctx, choice: int = -1):
        """Upsolve: The command ;upsolve lists all problems that you haven't solved in contests you participated 
        - Type ;upsolve for listing all available problems.
        - Type ;upsolve <nr> for choosing the problem <nr> as gitgud problem (only possible if you have no active gitgud challenge)
        - After solving the problem you can claim gitgud points for it with ;gotgud
        - If you can't solve the problem for 2 hours you can skip it with ;nogud
        - The all-time ranklist can be found with ;gitgudders
        - A monthly ranklist is shown when you type ;monthlygitgudders
        - Another way to gather gitgud points is ;gitgud (only works if you have no active gitgud-Challenge)
        - For help with each of the commands you can type ;help <command> (e.g. ;help gitgudders)
        
        Point distribution:
        delta  | <-300| -300 | -200 | -100 |  0  | +100 | +200 |>=300
        points |   1  |   2  |   3  |   5  |  8  |  12  |  17  |  23 
        """
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user = cf_common.user_db.fetch_cf_user(handle)
        rating = round(user.effective_rating, -2)
        rating = max(1100, rating)
        rating = min(3000, rating)
        resp = await cf.user.rating(handle=handle)
        contests = {change.contestId for change in resp}
        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions if sub.verdict == 'OK'}
        problems = [prob for prob in cf_common.cache2.problem_cache.problems
                    if prob.name not in solved and prob.contestId in contests]

        if not problems:
            raise CodeforcesCogError('Problems not found within the search parameters')

        problems.sort(key=lambda problem: problem.rating)

        if choice > 0 and choice <= len(problems):
            await self._validate_gitgud_status(ctx,delta=None)
            problem = problems[choice - 1]
            await self._gitgud(ctx, handle, problem, problem.rating - rating)
        else:
            problems = problems[:500]
              
            def make_line(i, prob):
                data = (f'{i + 1}: [{prob.name}]({prob.url}) [{prob.rating}]')
                return data

            def make_page(chunk, pi, num):
                title = f'Select a problem to upsolve (1-{num}):'
                msg = '\n'.join(make_line(10*pi+i, prob) for i, prob in enumerate(chunk))
                embed = discord_common.cf_color_embed(description=msg)
                return title, embed
                  
            pages = [make_page(chunk, pi, len(problems)) for pi, chunk in enumerate(paginator.chunkify(problems, 10))]
            paginator.paginate(self.bot, ctx.channel, pages, wait_time=5 * 60, set_pagenum_footers=True)   

    @commands.command(brief='Recommend a problem',
                      usage='[+tag..] [~tag..] [rating|rating1-rating2]')
    @cf_common.user_guard(group='gitgud')
    async def gimme(self, ctx, *args):
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        rating = round(cf_common.user_db.fetch_cf_user(handle).effective_rating, -2)
        tags = cf_common.parse_tags(args, prefix='+')
        bantags = cf_common.parse_tags(args, prefix='~')

        srating = round(cf_common.user_db.fetch_cf_user(handle).effective_rating, -2)
        erating = srating 
        for arg in args:
            if arg[0:3].isdigit():
                ratings = arg.split("-")
                srating = int(ratings[0])
                if (len(ratings) > 1): 
                    erating = int(ratings[1])
                else:
                    erating = srating

        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions if sub.verdict == 'OK'}

        problems = [prob for prob in cf_common.cache2.problem_cache.problems
                    if prob.rating >= srating and prob.rating <= erating and prob.name not in solved
                    and not cf_common.is_contest_writer(prob.contestId, handle)
                    and prob.matches_all_tags(tags)
                    and not prob.matches_any_tag(bantags)]

        if not problems:
            raise CodeforcesCogError('Problems not found within the search parameters')

        problems.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(
            problem.contestId).startTimeSeconds)

        choice = max([random.randrange(len(problems)) for _ in range(3)])
        problem = problems[choice]

        title = f'{problem.index}. {problem.name}'
        desc = cf_common.cache2.contest_cache.get_contest(problem.contestId).name
        embed = discord.Embed(title=title, url=problem.url, description=desc)
        ratingStr = problem.rating if srating == erating else '||'+str(problem.rating)+'||'
        embed.add_field(name='Rating', value=ratingStr)
        if tags:
            tagslist = ', '.join(problem.get_matched_tags(tags))
            embed.add_field(name='Matched tags', value=tagslist)
        await ctx.send(f'Recommended problem for `{handle}`', embed=embed)

    @commands.command(brief='List solved problems',
                      usage='[handles] [+hardest] [+practice] [+contest] [+virtual] [+outof] [+team] [+tag..] [~tag..] [r>=rating] [r<=rating] [d>=[[dd]mm]yyyy] [d<[[dd]mm]yyyy] [c+marker..] [i+index..]')
    async def stalk(self, ctx, *args):
        """Print problems solved by user sorted by time (default) or rating.
        All submission types are included by default (practice, contest, etc.)
        """
        (hardest,), args = cf_common.filter_flags(args, ['+hardest'])
        filt = cf_common.SubFilter(False)
        args = filt.parse(args)
        handles = args or ('!' + str(ctx.author),)
        handles = await cf_common.resolve_handles(ctx, self.converter, handles)
        submissions = [await cf.user.status(handle=handle) for handle in handles]
        submissions = [sub for subs in submissions for sub in subs]
        submissions = filt.filter_subs(submissions)

        if not submissions:
            raise CodeforcesCogError('Submissions not found within the search parameters')

        if hardest:
            submissions.sort(key=lambda sub: (sub.problem.rating or 0, sub.creationTimeSeconds), reverse=True)
        else:
            submissions.sort(key=lambda sub: sub.creationTimeSeconds, reverse=True)

        handlesWithUrl = ['`{}` (https://codeforces.com/profile/{})'.format(handle,handle) for handle in handles]

        def make_line(sub):
            data = (f'[{sub.problem.name}]({sub.problem.url})',
                    f'[{sub.problem.rating if sub.problem.rating else "?"}]',
                    f'({cf_common.days_ago(sub.creationTimeSeconds)})')
            return '\N{EN SPACE}'.join(data)

        def make_page(chunk):
            
            title = '{} solved problems by {}'.format('Hardest' if hardest else 'Recently',
                                                        ', '.join(handlesWithUrl))
            hist_str = '\n'.join(make_line(sub) for sub in chunk)
            embed = discord_common.cf_color_embed(description=hist_str)
            return title, embed

        pages = [make_page(chunk) for chunk in paginator.chunkify(submissions[:100], 10)]
        paginator.paginate(self.bot, ctx.channel, pages, wait_time=5 * 60, set_pagenum_footers=True)

    @commands.command(brief='Create a mashup', usage='[handles] [+tag..] [~tag..] [?[-]delta]')
    async def mashup(self, ctx, *args):
        """Create a mashup contest using problems within -200 and +400 of average rating of handles provided.
        Add tags with "+" before them.
        Ban tags with "~" before them.
        """
        delta = 100
        handles = [arg for arg in args if arg[0] not in '+~?']
        tags = cf_common.parse_tags(args, prefix='+')
        bantags = cf_common.parse_tags(args, prefix='~')
        deltaStr = [arg[1:] for arg in args if arg[0] == '?' and len(arg) > 1]
        if len(deltaStr) > 1:
            raise CodeforcesCogError('Only one delta argument is allowed')
        if len(deltaStr) == 1:
            try:
                delta += round(int(deltaStr[0]), -2)
            except ValueError:
                raise CodeforcesCogError('delta could not be interpreted as number')

        handles = handles or ('!' + str(ctx.author),)
        handles = await cf_common.resolve_handles(ctx, self.converter, handles)
        resp = [await cf.user.status(handle=handle) for handle in handles]
        submissions = [sub for user in resp for sub in user]
        solved = {sub.problem.name for sub in submissions}
        info = await cf.user.info(handles=handles)
        rating = int(round(sum(user.effective_rating for user in info) / len(handles), -2))
        rating += delta
        rating = max(800, rating)
        rating = min(3500, rating)
        problems = [prob for prob in cf_common.cache2.problem_cache.problems
                    if abs(prob.rating - rating) <= 300 and prob.name not in solved
                    and not any(cf_common.is_contest_writer(prob.contestId, handle) for handle in handles)
                    and not cf_common.is_nonstandard_problem(prob)
                    and prob.matches_all_tags(tags)
                    and not prob.matches_any_tag(bantags)]

        if len(problems) < 4:
            raise CodeforcesCogError('Problems not found within the search parameters')

        problems.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(
            problem.contestId).startTimeSeconds)

        choices = []
        for i in range(4):
            k = max(random.randrange(len(problems) - i) for _ in range(2))
            for c in choices:
                if k >= c:
                    k += 1
            choices.append(k)
            choices.sort()

        problems = sorted([problems[k] for k in choices], key=lambda problem: problem.rating)
        msg = '\n'.join(f'{"ABCD"[i]}: [{p.name}]({p.url}) [{p.rating}]' for i, p in enumerate(problems))
        str_handles = '`, `'.join(handles)
        embed = discord_common.cf_color_embed(description=msg)
        await ctx.send(f'Mashup contest for `{str_handles}`', embed=embed)
    


    @commands.command(brief='Challenge', aliases=['gitbad'],
                      usage='[delta=0|r=rating] [+tags...] [~tags...]')
    @cf_common.user_guard(group='gitgud')
    async def gitgud(self, ctx, *args):
        """Gitgud: You can request a problem from the bots relative to your current rating with ;gitgud <delta>
        - It is also possible to request problems with a certain tag now but you get less points for it: ;gitgud <delta>|r=<rating> [+tags...] [~tags...]
        - After solving the problem you can claim gitgud points for it with ;gotgud
        - If you can't solve the problem for 2 hours you can skip it with ;nogud
        - The all-time ranklist can be found with ;gitgudders
        - A monthly ranklist is shown when you type ;monthlygitgudders
        - Another way to gather gitgud points is ;upsolve (only works if you have no active gitgud-Challenge)
        - For help with each of the commands you can type ;help <command> (e.g. ;help gitgudders)
        
        Point distribution:
        delta  | <-300| -300 | -200 | -100 |   0  | +100 | +200 |>=300
        no tags|   1  |   2  |   3  |   5  |   8  |  12  |  17  |  23 
        delta  | <-100| -100 |   0  | +100 | +200 | +300 | +400 |>=500
        tags   |   1  |   2  |   3  |   5  |   8  |  12  |  17  |  23 
        """
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user = cf_common.user_db.fetch_cf_user(handle)
        rating = round(user.effective_rating, -2)
        rating = max(1100, rating)
        rating = min(3000, rating)
        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions}
        noguds = cf_common.user_db.get_noguds(ctx.message.author.id)
        delta = 0
        tags = cf_common.parse_tags(args, prefix='+')
        bantags = cf_common.parse_tags(args, prefix='~')
        
        for arg in args:
            if arg[0] == '-':
                if arg[1:].isdigit():
                    delta = int(arg)
            else:
                if arg[0:].isdigit():
                    delta = int(arg)
            if arg.startswith('r='):
                if arg[2:].isdigit():
                    delta = int(arg[2:]) - rating


        await self._validate_gitgud_status(ctx, delta)
        
        problems = [prob for prob in cf_common.cache2.problem_cache.problems
                    if (prob.rating == rating + delta 
                    and prob.name not in solved 
                    and prob.name not in noguds)
                    and prob.matches_all_tags(tags)
                    and not prob.matches_any_tag(bantags)]
                        

        def check(problem):
            return (not cf_common.is_nonstandard_problem(problem) and
                    not cf_common.is_contest_writer(problem.contestId, handle))

        problems = list(filter(check, problems))
        if not problems:
            raise CodeforcesCogError('No problem to assign')

        problems.sort(key=lambda problem: cf_common.cache2.contest_cache.get_contest(
            problem.contestId).startTimeSeconds)

        choice = max(random.randrange(len(problems)) for _ in range(5))
        if tags or bantags:
            delta = delta - 200
        await self._gitgud(ctx, handle, problems[choice], delta)

    @commands.command(brief='Print user gitgud history')
    async def gitlog(self, ctx, member: discord.Member = None):
        """Displays the list of gitgud problems issued to the specified member, excluding those noguded by admins.
        If the challenge was completed, time of completion and amount of points gained will also be displayed.
        """
        def make_line(entry):
            issue, finish, name, contest, index, delta, status = entry
            problem = cf_common.cache2.problem_cache.problem_by_name[name]
            line = f'[{name}]({problem.url})\N{EN SPACE}[{problem.rating}]'
            if finish:
                time_str = cf_common.days_ago(finish)
                points = f'{_calculateGitgudScoreForDelta(delta):+}'
                line += f'\N{EN SPACE}{time_str}\N{EN SPACE}[{points}]'
            return line

        def make_page(chunk,score):
            message = discord.utils.escape_mentions(f'Gitgud log for {member.display_name} (total score: {score})')
            log_str = '\n'.join(make_line(entry) for entry in chunk)
            embed = discord_common.cf_color_embed(description=log_str)
            return message, embed

        member = member or ctx.author
        data = cf_common.user_db.gitlog(member.id)
        if not data:
            raise CodeforcesCogError(f'{member.mention} has no gitgud history.')
        score = 0
        for entry in data:
            issue, finish, name, contest, index, delta, status = entry
            if finish:
                score+=_calculateGitgudScoreForDelta(delta)
     

        pages = [make_page(chunk, score) for chunk in paginator.chunkify(data, 10)]
        paginator.paginate(self.bot, ctx.channel, pages, wait_time=5 * 60, set_pagenum_footers=True)

    @commands.command(brief='Print user nogud history')
    async def nogudlog(self, ctx, member: discord.Member = None):
        """Displays the list of nogud problems issued to the specified member, excluding those noguded by admins.
        """
        def make_line(entry):
            issue, finish, name, contest, index, delta, status = entry
            problem = cf_common.cache2.problem_cache.problem_by_name[name]
            line = f'[{name}]({problem.url})\N{EN SPACE}[{problem.rating}]'
            if finish:
                time_str = cf_common.days_ago(finish)
                points = f'{_calculateGitgudScoreForDelta(delta):+}'
                line += f'\N{EN SPACE}{time_str}\N{EN SPACE}[{points}]'
            return line

        def make_page(chunk):
            message = discord.utils.escape_mentions(f'Nogud log for {member.display_name}')
            log_str = '\n'.join(make_line(entry) for entry in chunk)
            embed = discord_common.cf_color_embed(description=log_str)
            return message, embed

        member = member or ctx.author
        data = cf_common.user_db.gitlog(member.id)
        if not data:
            raise CodeforcesCogError(f'{member.mention} has no gitgud history.')

        data = [entry for entry in data if entry[1] is None]                

        pages = [make_page(chunk) for chunk in paginator.chunkify(data, 10)]
        paginator.paginate(self.bot, ctx.channel, pages, wait_time=5 * 60, set_pagenum_footers=True)

    @commands.command(brief='Report challenge completion', aliases=['gotbad'])
    @cf_common.user_guard(group='gitgud')
    async def gotgud(self, ctx):
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user_id = ctx.message.author.id
        active = cf_common.user_db.check_challenge(user_id)
        if not active:
            raise CodeforcesCogError(f'You do not have an active challenge')

        submissions = await cf.user.status(handle=handle)
        solved = {sub.problem.name for sub in submissions if sub.verdict == 'OK'}

        challenge_id, issue_time, name, contestId, index, delta = active
        if not name in solved:
            raise CodeforcesCogError('You haven\'t completed your challenge.')

        score = _calculateGitgudScoreForDelta(delta)
        finish_time = int(datetime.datetime.now().timestamp())
        rc = cf_common.user_db.complete_challenge(user_id, challenge_id, finish_time, score)

        now = datetime.datetime.now()
        start_time, end_time = cf_common.get_start_and_end_of_month(now)
        now_time = int(now.timestamp())

        morePointsActive = self._check_more_points_active(now_time, start_time, end_time)
        
        monthlyPoints = 2 * score if morePointsActive else score

        if rc == 1:
            duration = cf_common.pretty_time_format(finish_time - issue_time)
            await ctx.send(f'Challenge completed in {duration}. {handle} gained {score} alltime ranklist points and {monthlyPoints} monthly ranklist points.')
        else:
            await ctx.send('You have already claimed your points')

    @commands.command(brief='Skip challenge', aliases=['toobad'])
    @cf_common.user_guard(group='gitgud')
    async def nogud(self, ctx):
        await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        user_id = ctx.message.author.id
        active = cf_common.user_db.check_challenge(user_id)
        if not active:
            raise CodeforcesCogError(f'You do not have an active challenge')

        challenge_id, issue_time, name, contestId, index, delta = active
        finish_time = int(datetime.datetime.now().timestamp())
        if finish_time - issue_time < _GITGUD_NO_SKIP_TIME:
            skip_time = cf_common.pretty_time_format(issue_time + _GITGUD_NO_SKIP_TIME - finish_time)
            await ctx.send(f'Think more. You can skip your challenge in {skip_time}.')
            return
        cf_common.user_db.skip_challenge(user_id, challenge_id, Gitgud.NOGUD)
        await ctx.send(f'Challenge skipped.')

    @commands.command(brief='Force skip a challenge')
    @cf_common.user_guard(group='gitgud')
    @commands.has_any_role(constants.TLE_ADMIN, constants.TLE_MODERATOR)
    async def _nogud(self, ctx, member: discord.Member):
        active = cf_common.user_db.check_challenge(member.id)
        rc = cf_common.user_db.skip_challenge(member.id, active[0], Gitgud.FORCED_NOGUD)
        if rc == 1:
            await ctx.send(f'Challenge skip forced.')
        else:
            await ctx.send(f'Failed to force challenge skip.')

    @commands.command(brief='Recommend a contest', usage='[handles...] [+pattern...]')
    async def vc(self, ctx, *args: str):
        """Recommends a contest based on Codeforces rating of the handle provided.
        e.g ;vc mblazev c1729 +global +hello +goodbye +avito"""
        markers = [x for x in args if x[0] == '+']
        handles = [x for x in args if x[0] != '+'] or ('!' + str(ctx.author),)
        handles = await cf_common.resolve_handles(ctx, self.converter, handles, maxcnt=25)
        info = await cf.user.info(handles=handles)
        contests = cf_common.cache2.contest_cache.get_contests_in_phase('FINISHED')

        if not markers:
            divr = sum(user.effective_rating for user in info) / len(handles)
            div1_indicators = ['div1', 'global', 'avito', 'goodbye', 'hello']
            markers = ['div3'] if divr < 1600 else ['div2'] if divr < 2100 else div1_indicators

        recommendations = {contest.id for contest in contests if
                           contest.matches(markers) and
                           not cf_common.is_nonstandard_contest(contest) and
                           not any(cf_common.is_contest_writer(contest.id, handle)
                                       for handle in handles)}

        # Discard contests in which user has non-CE submissions.
        visited_contests = await cf_common.get_visited_contests(handles)
        recommendations -= visited_contests

        if not recommendations:
            raise CodeforcesCogError('Unable to recommend a contest')

        recommendations = list(recommendations)
        recommendations.sort(key=lambda contest: cf_common.cache2.contest_cache.get_contest(contest).startTimeSeconds, reverse=True)
        contests = [cf_common.cache2.contest_cache.get_contest(contest_id) for contest_id in recommendations[:25]]

        def make_line(c):
            return f'[{c.name}]({c.url}) {cf_common.pretty_time_format(c.durationSeconds)}'

        def make_page(chunk):
            str_handles = '`, `'.join(handles)
            message = f'Recommended contest(s) for `{str_handles}`'
            vc_str = '\n'.join(make_line(contest) for contest in chunk)
            embed = discord_common.cf_color_embed(description=vc_str)
            return message, embed

        pages = [make_page(chunk) for chunk in paginator.chunkify(contests, 5)]
        paginator.paginate(self.bot, ctx.channel, pages, wait_time=5 * 60, set_pagenum_footers=True)

    @commands.command(brief="Display unsolved rounds closest to completion", usage='[keywords]')
    async def fullsolve(self, ctx, *args: str):
        """Displays a list of contests, sorted by number of unsolved problems.
        Contest names matching any of the provided tags will be considered. e.g ;fullsolve +edu"""
        handle, = await cf_common.resolve_handles(ctx, self.converter, ('!' + str(ctx.author),))
        tags = [x for x in args if x[0] == '+']

        problem_to_contests = cf_common.cache2.problemset_cache.problem_to_contests
        contests = [contest for contest in cf_common.cache2.contest_cache.get_contests_in_phase('FINISHED')
                    if (not tags or contest.matches(tags)) and not cf_common.is_nonstandard_contest(contest)]

        # subs_by_contest_id contains contest_id mapped to [list of problem.name]
        subs_by_contest_id = defaultdict(set)
        for sub in await cf.user.status(handle=handle):
            if sub.verdict == 'OK':
                try:
                    contest = cf_common.cache2.contest_cache.get_contest(sub.problem.contestId)
                    problem_id = (sub.problem.name, contest.startTimeSeconds)
                    for contestId in problem_to_contests[problem_id]:
                        subs_by_contest_id[contestId].add(sub.problem.name)
                except cache_system2.ContestNotFound:
                    pass

        contest_unsolved_pairs = []
        for contest in contests:
            num_solved = len(subs_by_contest_id[contest.id])
            try:
                num_problems = len(cf_common.cache2.problemset_cache.get_problemset(contest.id))
                if 0 < num_solved < num_problems:
                    contest_unsolved_pairs.append((contest, num_solved, num_problems))
            except cache_system2.ProblemsetNotCached:
                # In case of recent contents or cetain bugged contests
                pass

        contest_unsolved_pairs.sort(key=lambda p: (p[2] - p[1], -p[0].startTimeSeconds))

        if not contest_unsolved_pairs:
            raise CodeforcesCogError(f'`{handle}` has no contests to fullsolve :confetti_ball:')

        def make_line(entry):
            contest, solved, total = entry
            return f'[{contest.name}]({contest.url})\N{EN SPACE}[{solved}/{total}]'

        def make_page(chunk):
            message = f'Fullsolve list for `{handle}`'
            full_solve_list = '\n'.join(make_line(entry) for entry in chunk)
            embed = discord_common.cf_color_embed(description=full_solve_list)
            return message, embed

        pages = [make_page(chunk) for chunk in paginator.chunkify(contest_unsolved_pairs, 10)]
        paginator.paginate(self.bot, ctx.channel, pages, wait_time=5 * 60, set_pagenum_footers=True)

    @staticmethod
    def getEloWinProbability(ra: float, rb: float) -> float:
        return 1.0 / (1 + 10**((rb - ra) / 400.0))

    @staticmethod
    def composeRatings(left: float, right: float, ratings: List[float]) -> int:
        for tt in range(20):
            r = (left + right) / 2.0

            rWinsProbability = 1.0
            for rating, count in ratings:
                rWinsProbability *= Codeforces.getEloWinProbability(r, rating)**count

            if rWinsProbability < 0.5:
                left = r
            else:
                right = r
        return round((left + right) / 2)

    @commands.command(brief='Calculate team rating', usage='[handles] [+peak]')
    async def teamrate(self, ctx, *args: str):
        """Provides the combined rating of the entire team.
        If +server is provided as the only handle, will display the rating of the entire server.
        Supports multipliers. e.g: ;teamrate gamegame*1000"""

        (is_entire_server, peak), handles = cf_common.filter_flags(args, ['+server', '+peak'])
        handles = handles or ('!' + str(ctx.author),)

        def rating(user):
            return user.maxRating if peak else user.rating

        if is_entire_server:
            res = cf_common.user_db.get_cf_users_for_guild(ctx.guild.id)
            ratings = [(rating(user), 1) for user_id, user in res if user.rating is not None]
            user_str = '+server'
        else:
            def normalize(x):
                return [i.lower() for i in x]
            handle_counts = {}
            parsed_handles = []
            for i in handles:
                parse_str = normalize(i.split('*'))
                if len(parse_str) > 1:
                    try:
                        handle_counts[parse_str[0]] = int(parse_str[1])
                    except ValueError:
                        raise CodeforcesCogError("Can't multiply by non-integer")
                else:
                    handle_counts[parse_str[0]] = 1
                parsed_handles.append(parse_str[0])

            cf_handles = await cf_common.resolve_handles(ctx, self.converter, parsed_handles, mincnt=1, maxcnt=1000)
            cf_handles = normalize(cf_handles)
            cf_to_original = {a: b for a, b in zip(cf_handles, parsed_handles)}
            original_to_cf = {a: b for a, b in zip(parsed_handles, cf_handles)}
            users = await cf.user.info(handles=cf_handles)
            user_strs = []
            for a, b in handle_counts.items():
                if b > 1:
                    user_strs.append(f'{original_to_cf[a]}*{b}')
                elif b == 1:
                    user_strs.append(original_to_cf[a])
                elif b <= 0:
                    raise CodeforcesCogError('How can you have nonpositive members in team?')

            user_str = ', '.join(user_strs)
            ratings = [(rating(user), handle_counts[cf_to_original[user.handle.lower()]])
                       for user in users if user.rating]

        if len(ratings) == 0:
            raise CodeforcesCogError("No CF usernames with ratings passed in.")

        left = -100.0
        right = 10000.0
        teamRating = Codeforces.composeRatings(left, right, ratings)
        embed = discord.Embed(title=user_str, description=teamRating, color=cf.rating2rank(teamRating).color_embed)
        await ctx.send(embed = embed)

    @discord_common.send_error_if(CodeforcesCogError, cf_common.ResolveHandleError,
                                  cf_common.FilterError)
    async def cog_command_error(self, ctx, error):
        pass


async def setup(bot):
    await bot.add_cog(Codeforces(bot))
