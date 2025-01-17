from typing import Callable, List, Optional

import discord


def example_callback(embeds):
    def callback(page):
        return embeds[page - 1]

    return callback


class Paginator(discord.ui.View):
    r"""A dynamic paginator that uses a callback to generate embeds.
    This should be passed in as a regular view to methods like
    :meth:`discord.abc.Messageable.send`.
    Parameters
    -----------
    callback: Callable[[:class:`int`], List[:class:`discord.Embed`]]
        The callback that takes in a page number and returns a list of
        :class:`discord.Embed`\s.
    pages: :class:`int`
        The page count, i.e. the last page the callback can generate.
    Attributes
    -----------
    page: :class:`int`
        The current page on the paginator.
    """

    def __init__(
        self, callback: Callable[[int], List[discord.Embed]], pages: int, **kwargs
    ):
        super().__init__(**kwargs)
        self.pages = pages
        self.callback = callback

        self.page = 1
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.pages

    def get_page(self, page: int) -> List[discord.Embed]:
        """Returns a page generated by the callback. Technically
        an alias for `Paginator.callback()`.
        Useful for getting an embed before deploying a View.
        """

        return self.callback(page)

    @discord.ui.button(label="Back")
    async def prev_button(self, interaction, _):
        self.page = max(self.page - 1, 1)
        self._update_buttons()
        embs = self.callback(self.page)
        await interaction.response.edit_message(embeds=[embs], view=self)

    @discord.ui.button(label="Next")
    async def next_button(self, interaction, _):
        self.page = min(self.page + 1, self.pages)
        self._update_buttons()
        embs = self.callback(self.page)
        await interaction.response.edit_message(embeds=[embs], view=self)


class StaticPaginator(Paginator):
    """A simple paginator that takes in lines instead of a callback.
    A line limit and base embed may be passed in for customization.

    Parameters
    -----------
    lines: List[:class:`str`]
        The list of strings to iterate through in the paginator,
        joined in the output embed's description with newlines.
    line_limit: Optional[:class:`int`]
        The amount of lines to display per page. Defaults to 15.
    base_embed: Optional[:class:`discord.Embed`]
        The template for the resulting embed. Only the description will
        be replaced.
    """

    def __init__(
        self,
        lines: List[str],
        *,
        line_limit: Optional[int] = 15,
        base_embed: Optional[discord.Embed] = None,
        **kwargs
    ):
        self.lines = lines
        self.line_limit = line_limit
        self.base_embed = base_embed or discord.Embed()

        import math

        pages: int = math.ceil(len(lines) / self.line_limit)  # type: ignore

        def callback(page: int) -> List[discord.Embed]:
            m = (page - 1) * self.line_limit  # type: ignore
            n = page * self.line_limit  # type: ignore

            emb = self.base_embed.copy()
            emb.description = "\n".join(self.lines[m:n])
            return [emb]

        super().__init__(callback, pages, **kwargs)
