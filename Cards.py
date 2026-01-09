import random


class Card:
    """
        Represents a single playing card in a standard 52-card deck.
    """
    def __init__(self, suit, rank):
        """
                Initializes a new Card instance.

                Args:
                    suit (int): The suit of the card (1=Hearts, 2=Diamonds, 3=Clubs, 4=Spades).
                    rank (int): The rank of the card (1=Ace, 2-10=Number, 11=Jack, 12=Queen, 13=King).
        """
        self.suit = suit
        self.rank = rank

    def get_value(self):
        """
                Calculates the Blackjack value of the card.

                Rules:
                - Ace (1): Returns 11
                - Face cards (11, 12, 13): Return 10.
                - Number cards (2-10): Return their face value.

                Returns:
                    int: The point value of the card.
        """
        if self.rank == 1:
            return 11
        elif 11 <= self.rank <= 13:
            return 10
        else:
            return self.rank


class Deck:
    """
        Represents a standard deck of 52 playing cards.
    """
    def __init__(self):
        """
                Initializes a new Deck.
                Automatically builds the deck upon creation.
        """
        self.cards = []  # list of cards
        self.build_deck()

    def build_deck(self):
        """
                Populates the deck with 52 cards.
                4 suits x 13 ranks.
        """
        # create deck

        # "Hearts" 1, "Diamonds" 2, "Clubs" 3, "Spades" 4
        suits = [1, 2, 3, 4]
        ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

        self.cards = []
        for suit in suits:
            for rank in ranks:
                self.cards.append(Card(suit, rank))

    def shuffle(self):
        """
                Randomizes the order of the cards in the deck.
        """
        random.shuffle(self.cards)

    def deal_one(self):
        """
                Removes and returns the top card from the deck.

                Returns:
                    Card: The card object that was removed.
                    None: If the deck is empty.
        """
        if len(self.cards) > 0:
            return self.cards.pop()
        else:
            return None  # או לערבב מחדש אם נגמרו הקלפים
