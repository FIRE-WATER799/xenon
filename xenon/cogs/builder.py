from discord.ext import commands as cmd
import asyncio
import discord

from utils import helpers


def create_permissions(**kwargs):
    permissions = discord.Permissions.none()
    permissions.update(**kwargs)
    return permissions


class BuildMenu:
    def __init__(self, ctx):
        self.ctx = ctx
        self.msg = None
        self.page = 1
        self.pages = [
            {
                "name": "roles",
                "options": [
                    ["delete_old_roles", True],
                    ["staff_roles", True],
                    ["muted_role", True],
                    ["color_roles", False],
                    ["game_specific_roles", False]
                ]
            },
            {
                "name": "channels",
                "options": [
                    ["delete_old_channels", True],
                    ["info_channels", True],
                    ["staff_channels", True],
                    ["general_channels", True],
                    ["development_channels", False],
                    ["gaming_channels", False],
                    ["afk_channel", False]
                ]
            }
        ]

    async def update(self):
        await self.msg.edit(embed=self._create_embed())

    async def run(self):
        self.msg = await self.ctx.send(embed=self._create_embed())

        options = {
            **{f"{i + 1}\u20e3": self._switch_option(i) for i in range(9)},
            "◀": self._prev_page,
            "▶": self._next_page,
            "❎": self._cancel,
            "✅": self._finish,
        }

        for option in options:
            await self.msg.add_reaction(option)

        try:
            async for reaction, user in helpers.IterWaitFor(
                    self.ctx.bot,
                    event="reaction_add",
                    check=lambda r, u: u.id == self.ctx.author.id and
                                       r.message.id == self.msg.id and
                                       str(r.emoji) in options.keys(),
                    timeout=3 * 60
            ):
                try:
                    await self.msg.remove_reaction(reaction.emoji, user)
                except Exception:
                    pass

                if not await options[str(reaction.emoji)]():
                    try:
                        await self.msg.clear_reactions()
                    except Exception:
                        pass

                    return {name: value for page in self.pages for name, value in page["options"]}

                await self.update()
        except asyncio.TimeoutError:
            try:
                await self.msg.clear_reactions()
            except Exception:
                pass

            raise cmd.CommandError("timeout")

    async def _next_page(self):
        if self.page < len(self.pages):
            self.page += 1

        return True

    async def _prev_page(self):
        if self.page > 1:
            self.page -= 1

        return True

    def _switch_option(self, option):
        async def predicate():
            try:
                self.pages[self.page - 1]["options"][option][1] = not self.pages[self.page - 1]["options"][option][1]
            except IndexError:
                pass

            return True

        return predicate

    async def _cancel(self):
        try:
            await self.msg.clear_reactions()
        except Exception:
            pass
        raise cmd.CommandError("canceled")

    async def _finish(self):
        return False

    def _create_embed(self):
        page_options = self.pages[self.page - 1]
        embed = self.ctx.em("", title="Server Builder")["embed"]
        embed.title = page_options["name"].title()
        for i, (name, value) in enumerate(page_options["options"]):
            embed.description += f"{i + 1}\u20e3 **{name.replace('_', ' ').title()}** -> {'✅' if value else '❌'}\n"

        return embed


class Builder(cmd.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cmd.command(aliases=["builder", "bld", "bd"], hidden=True)
    async def build(self, ctx):
        menu = BuildMenu(ctx)
        options = await menu.run()

        roles = {"staff": [], "muted": []}

        if options["delete_old_channels"]:
            for channel in ctx.guild.channels:
                await channel.delete()

        if options["delete_old_roles"]:
            for role in filter(lambda r: not r.managed and not r.is_default(), ctx.guild.roles):
                await role.delete()

        if options["staff_roles"]:
            staff_roles = [
                {
                    "name": "Owner",
                    "color": discord.Color.blurple(),
                    "permissions": discord.Permissions.all()
                },
                {
                    "name": "Admin",
                    "color": discord.Color.dark_red(),
                    "permissions": discord.Permissions.all()
                },
                {
                    "name": "Moderator",
                    "color": discord.Color.teal(),
                    "permissions": create_permissions(
                        kick_members=True,
                        ban_members=True,
                        view_audit_log=True,
                        priority_speaker=True,
                        mute_members=True,
                        deafen_members=True,
                        move_members=True,
                        manage_nicknames=True
                    )
                }
            ]

            for kwargs in staff_roles:
                roles["staff"].append(await ctx.guild.create_role(**kwargs))

        if options["muted_role"]:
            roles["muted"].append(await ctx.guild.create_role(
                name="Muted",
                color=discord.Color.dark_grey(),
                permissions=create_permissions(
                    send_messages=False,
                    add_reactions=False,
                    connect=False
                )
            ))

        if options["color_roles"]:
            color_roles = [
                {
                    "name": "Green",
                    "color": discord.Color.green()
                },
                {
                    "name": "Blue",
                    "color": discord.Color.blue()
                },
                {
                    "name": "Purple",
                    "color": discord.Color.purple()
                },
                {
                    "name": "Magenta",
                    "color": discord.Color.magenta()
                },
                {
                    "name": "Orange",
                    "color": discord.Color.orange()
                },
                {
                    "name": "Red",
                    "color": discord.Color.red()
                },
            ]

            for kwargs in color_roles:
                await ctx.guild.create_role(**kwargs)

        if options["game_specific_roles"]:
            game_roles = ["minecraft", "fortnite", "pubg", "roblox"]
            for name in game_roles:
                await ctx.guild.create_role(name=name)

        if options["info_channels"]:
            info_category = await ctx.guild.create_category(
                name="Info",
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        send_messages=False
                    ),
                    **{role: discord.PermissionOverwrite(
                        send_messages=True
                    ) for role in roles["staff"]}
                }
            )

            channels = ["announcements", "faq", "rules"]
            for name in channels:
                await info_category.create_text_channel(name=name)

        if options["staff_channels"]:
            staff_category = await ctx.guild.create_category(
                name="Staff",
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        read_messages=False,
                        send_messages=False,
                        connect=False
                    ),
                    **{role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        connect=True
                    ) for role in roles["staff"]}
                }
            )

            text_channels = ["staff general", "staff commands"]
            for name in text_channels:
                await staff_category.create_text_channel(name=name)

            await staff_category.create_voice_channel(name="Staff Voice")

        if options["general_channels"]:
            general_category = await ctx.guild.create_category(
                name="General",
                overwrites={role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False,
                    connect=False
                ) for role in roles["muted"]}
            )

            text_channels = ["general", "shitpost", "commands"]
            for name in text_channels:
                await general_category.create_text_channel(name=name)

            await general_category.create_voice_channel(name="General")

        if options["development_channels"]:
            dev_category = await ctx.guild.create_category(
                name="Development",
                overwrites={role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False,
                    connect=False
                ) for role in roles["muted"]}
            )

            text_channels = ["python", "javascript", "java", "kotlin", "c", "go", "ruby"]
            for name in text_channels:
                await dev_category.create_text_channel(name=name)

        if options["gaming_channels"]:
            game_category = await ctx.guild.create_category(
                name="Gaming",
                overwrites={role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False,
                    connect=False
                ) for role in roles["muted"]}
            )

            text_channels = ["gaming general", "team finding"]
            for name in text_channels:
                await game_category.create_text_channel(name=name)

            voice_channels = [
                {
                    "name": "Free 1"
                },
                {
                    "name": "Free 2"
                },
                {
                    "name": "Duo 1",
                    "user_limit": 2
                },
                {
                    "name": "Duo 2",
                    "user_limit": 2
                },
                {
                    "name": "Trio 1",
                    "user_limit": 3
                },
                {
                    "name": "Trio 2",
                    "user_limit": 3
                },
                {
                    "name": "Squad 1",
                    "user_limit": 4
                },
                {
                    "name": "Squad 2",
                    "user_limit": 4
                }
            ]
            for kwargs in voice_channels:
                await game_category.create_voice_channel(**kwargs)

        if options["afk_channel"]:
            afk_category = await ctx.guild.create_category(
                name="AFK",
                overwrites={role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False,
                    connect=False
                ) for role in roles["muted"]}
            )

            afk_channel = await afk_category.create_voice_channel(name="Afk")
            await ctx.guild.edit(afk_channel=afk_channel)


def setup(bot):
    bot.add_cog(Builder(bot))