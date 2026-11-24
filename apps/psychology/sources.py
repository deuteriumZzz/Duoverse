# ruff: noqa: E501 — one bibliographic record per line reads best
"""Published research behind the scientific layer. Every entry was checked against Crossref (authors, year, journal,
volume, pages, DOI) or the publisher; texts in the knowledge base cite these keys in data["sources"].
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    short: str  # how a reader sees it under a text
    full: str
    url: str  # DOI or a page we opened; empty for books without one


def _doi(doi: str) -> str:
    return f"https://doi.org/{doi}"


SOURCES: dict[str, Source] = {
    # measurement
    "donnellan2006": Source("Donnellan et al., 2006", "Donnellan, M. B., Oswald, F. L., Baird, B. M., & Lucas, R. E. (2006). The Mini-IPIP scales: Tiny-yet-effective measures of the Big Five factors of personality. Psychological Assessment, 18(2), 192–203.", _doi("10.1037/1040-3590.18.2.192")),
    "fraley2000": Source("Fraley, Waller & Brennan, 2000", "Fraley, R. C., Waller, N. G., & Brennan, K. A. (2000). An item response theory analysis of self-report measures of adult attachment. Journal of Personality and Social Psychology, 78(2), 350–365.", _doi("10.1037/0022-3514.78.2.350")),
    # personality and couples
    "malouff2010": Source("Malouff et al., 2010", "Malouff, J. M., Thorsteinsson, E. B., Schutte, N. S., Bhullar, N., & Rooke, S. E. (2010). The Five-Factor Model of personality and relationship satisfaction of intimate partners: A meta-analysis. Journal of Research in Personality, 44(1), 124–127.", _doi("10.1016/j.jrp.2009.09.004")),
    "weidmann2016": Source("Weidmann, Ledermann & Grob, 2016", "Weidmann, R., Ledermann, T., & Grob, A. (2016). The interdependence of personality and satisfaction in couples: A review. European Psychologist, 21(4), 284–295.", _doi("10.1027/1016-9040/a000261")),
    "karney1995": Source("Karney & Bradbury, 1995", "Karney, B. R., & Bradbury, T. N. (1995). The longitudinal course of marital quality and stability: A review of theory, method, and research. Psychological Bulletin, 118(1), 3–34.", _doi("10.1037/0033-2909.118.1.3")),
    "joel2020": Source("Joel et al., 2020", "Joel, S., Eastwick, P. W., Allison, C. J., Arriaga, X. B., Baker, Z. G., et al. (2020). Machine learning uncovers the most robust self-report predictors of relationship quality across 43 longitudinal couples studies. PNAS, 117(32), 19061–19071.", _doi("10.1073/pnas.1917036117")),
    # attachment
    "hazan1987": Source("Hazan & Shaver, 1987", "Hazan, C., & Shaver, P. (1987). Romantic love conceptualized as an attachment process. Journal of Personality and Social Psychology, 52(3), 511–524.", _doi("10.1037/0022-3514.52.3.511")),
    "bartholomew1991": Source("Bartholomew & Horowitz, 1991", "Bartholomew, K., & Horowitz, L. M. (1991). Attachment styles among young adults: A test of a four-category model. Journal of Personality and Social Psychology, 61(2), 226–244.", _doi("10.1037/0022-3514.61.2.226")),
    "li2012": Source("Li & Chan, 2012", "Li, T., & Chan, D. K.-S. (2012). How anxious and avoidant attachment affect romantic relationship quality differently: A meta-analytic review. European Journal of Social Psychology, 42(4), 406–419.", _doi("10.1002/ejsp.1842")),
    "simpson2017": Source("Simpson & Rholes, 2017", "Simpson, J. A., & Rholes, W. S. (2017). Adult attachment, stress, and romantic relationships. Current Opinion in Psychology, 13, 19–24.", _doi("10.1016/j.copsyc.2016.04.006")),
    "mikulincer2007": Source("Mikulincer & Shaver, 2007", "Mikulincer, M., & Shaver, P. R. (2007). Attachment in adulthood: Structure, dynamics, and change. Guilford Press.", ""),
    # conflict (Gottman and others)
    "gottman1992": Source("Gottman & Levenson, 1992", "Gottman, J. M., & Levenson, R. W. (1992). Marital processes predictive of later dissolution: Behavior, physiology, and health. Journal of Personality and Social Psychology, 63(2), 221–233.", _doi("10.1037/0022-3514.63.2.221")),
    "gottman1998": Source("Gottman et al., 1998", "Gottman, J. M., Coan, J., Carrere, S., & Swanson, C. (1998). Predicting marital happiness and stability from newlywed interactions. Journal of Marriage and the Family, 60(1), 5–22.", _doi("10.2307/353438")),
    "gottman2000": Source("Gottman & Levenson, 2000", "Gottman, J. M., & Levenson, R. W. (2000). The timing of divorce: Predicting when a couple will divorce over a 14-year period. Journal of Marriage and Family, 62(3), 737–745.", _doi("10.1111/j.1741-3737.2000.00737.x")),
    "gottman1994": Source("Gottman, 1994", "Gottman, J. M. (1994). What predicts divorce? The relationship between marital processes and marital outcomes. Lawrence Erlbaum (переиздание: Routledge, 2023).", _doi("10.4324/9781003429807")),
    "gottman_antidotes": Source("The Gottman Institute, 2013", "The Gottman Institute (2013). The Four Horsemen: The Antidotes. gottman.com.", "https://www.gottman.com/blog/the-four-horsemen-the-antidotes/"),
    "driver2004": Source("Driver & Gottman, 2004", "Driver, J. L., & Gottman, J. M. (2004). Daily marital interactions and positive affect during marital conflict among newlywed couples. Family Process, 43(3), 301–314.", _doi("10.1111/j.1545-5300.2004.00024.x")),
    "overall2017": Source("Overall & McNulty, 2017", "Overall, N. C., & McNulty, J. K. (2017). What type of communication during conflict is beneficial for intimate relationships? Current Opinion in Psychology, 13, 1–5.", _doi("10.1016/j.copsyc.2016.03.002")),
    "wiebe2016": Source("Wiebe & Johnson, 2016", "Wiebe, S. A., & Johnson, S. M. (2016). A review of the research in emotionally focused therapy for couples. Family Process, 55(3), 390–407.", _doi("10.1111/famp.12229")),
    "johnson2008": Source("Johnson, 2008", "Johnson, S. M. (2008). Hold me tight: Seven conversations for a lifetime of love. Little, Brown.", ""),
    # what helps
    "gable2004": Source("Gable et al., 2004", "Gable, S. L., Reis, H. T., Impett, E. A., & Asher, E. R. (2004). What do you do when things go right? The intrapersonal and interpersonal benefits of sharing positive events. Journal of Personality and Social Psychology, 87(2), 228–245.", _doi("10.1037/0022-3514.87.2.228")),
    "aron2000": Source("Aron et al., 2000", "Aron, A., Norman, C. C., Aron, E. N., McKenna, C., & Heyman, R. E. (2000). Couples' shared participation in novel and arousing activities and experienced relationship quality. Journal of Personality and Social Psychology, 78(2), 273–284.", _doi("10.1037/0022-3514.78.2.273")),
    "algoe2012": Source("Algoe, 2012", "Algoe, S. B. (2012). Find, remind, and bind: The functions of gratitude in everyday relationships. Social and Personality Psychology Compass, 6(6), 455–469.", _doi("10.1111/j.1751-9004.2012.00439.x")),
    "feeney2015": Source("Feeney & Collins, 2015", "Feeney, B. C., & Collins, N. L. (2015). A new look at social support: A theoretical perspective on thriving through relationships. Personality and Social Psychology Review, 19(2), 113–147.", _doi("10.1177/1088868314544222")),
    "muise2013": Source("Muise et al., 2013", "Muise, A., Impett, E. A., Kogan, A., & Desmarais, S. (2013). Keeping the spark alive: Being motivated to meet a partner's sexual needs sustains sexual desire in long-term romantic relationships. Social Psychological and Personality Science, 4(3), 267–273.", _doi("10.1177/1948550612457185")),
    "impett2005": Source("Impett, Gable & Peplau, 2005", "Impett, E. A., Gable, S. L., & Peplau, L. A. (2005). Giving up and giving in: The costs and benefits of daily sacrifice in intimate relationships. Journal of Personality and Social Psychology, 89(3), 327–344.", _doi("10.1037/0022-3514.89.3.327")),
    "murray1996": Source("Murray, Holmes & Griffin, 1996", "Murray, S. L., Holmes, J. G., & Griffin, D. W. (1996). The benefits of positive illusions: Idealization and the construction of satisfaction in close relationships. Journal of Personality and Social Psychology, 70(1), 79–98.", _doi("10.1037/0022-3514.70.1.79")),
    "rusbult1998": Source("Rusbult, Martz & Agnew, 1998", "Rusbult, C. E., Martz, J. M., & Agnew, C. R. (1998). The Investment Model Scale: Measuring commitment level, satisfaction level, quality of alternatives, and investment size. Personal Relationships, 5(4), 357–387.", _doi("10.1111/j.1475-6811.1998.tb00177.x")),
    "le2010": Source("Le et al., 2010", "Le, B., Dove, N. L., Agnew, C. R., Korn, M. S., & Mutso, A. A. (2010). Predicting nonmarital romantic relationship dissolution: A meta-analytic synthesis. Personal Relationships, 17(3), 377–390.", _doi("10.1111/j.1475-6811.2010.01285.x")),
    "dew2012": Source("Dew, Britt & Huston, 2012", "Dew, J., Britt, S., & Huston, S. (2012). Examining the relationship between financial issues and divorce. Family Relations, 61(4), 615–628.", _doi("10.1111/j.1741-3729.2012.00715.x")),
    "holt2017": Source("Holt-Lunstad, Robles & Sbarra, 2017", "Holt-Lunstad, J., Robles, T. F., & Sbarra, D. A. (2017). Advancing social connection as a public health priority in the United States. American Psychologist, 72(6), 517–530.", _doi("10.1037/amp0000103")),
    # the 36 questions and the love-languages review
    "aron1997": Source("Aron et al., 1997", "Aron, A., Melinat, E., Aron, E. N., Vallone, R. D., & Bator, R. J. (1997). The experimental generation of interpersonal closeness: A procedure and some preliminary findings. Personality and Social Psychology Bulletin, 23(4), 363–377.", _doi("10.1177/0146167297234003")),
    "impett2024": Source("Impett, Park & Muise, 2024", "Impett, E. A., Park, H. G., & Muise, A. (2024). Popular psychology through a scientific lens: Evaluating love languages from a relationship science perspective. Current Directions in Psychological Science, 33(2), 87–92.", _doi("10.1177/09637214231217663")),
}  # fmt: skip


def cite(keys: list[str]) -> list[Source]:
    """Known sources for a text, in the order given; unknown keys are skipped (the catalog test catches them)."""
    return [SOURCES[k] for k in keys if k in SOURCES]
